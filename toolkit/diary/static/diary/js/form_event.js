// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-input"
// Extracted from form_event.html's two inline <script> blocks (September 2026 quality pass).
// Wrapped as a factory function taking an options object (following session_detail.js's
// precedent, given how many values are threaded through from the template): four
// {% if %}-gated IIFEs (structured cost terms, ticket-link guidance, tag-description
// tooltips, top-5 tag bolding) became `if (opts.xxx) { ... }` guards, keeping the same
// "only run this code when the server says there's something to show" behaviour. The two
// original <script> tags are merged into this one factory call -- each kept its own IIFE
// wrapper internally, so variable scoping between them is unchanged (no risk of the
// break-even/crop-tool block and the OMDb film-search block colliding on a name).
function formEvent(opts) {
  "use strict";

  var COPY_LIMIT = opts.copySummaryMaxChars;

  $(document).ready(function() {
    var copy_summary = $('#id_copy_summary');
    var copy_summary_label = $('div#div_id_copy_summary label');
    var count_span;

    copy_summary_label.html("Copy summary:<br>(<span id='remaining_chars'></span>)");
    count_span = $('#remaining_chars');

    // Word counter element inserted below the textarea
    copy_summary.after('<div id="word-counter" aria-live="polite"></div>');
    var word_counter = $('#word-counter');

    function count_words(text) {
        return text.trim() === '' ? 0 : text.trim().split(/\s+/).length;
    }

    function update_character_count() {
        var used = copy_summary.val().length;
        var remaining = COPY_LIMIT - used;
        if(remaining < 0) {
            count_span.html(used + " characters, " + (used - COPY_LIMIT) + " over limit");
        } else {
            count_span.text(remaining + " remaining");
        }
    }

    function update_word_count() {
        var words = count_words(copy_summary.val());
        var cls, msg;
        if (words < 20) {
            cls = 'wc-composing';
            msg = words + ' words';
        } else if (words < 25) {
            cls = 'wc-close';
            msg = words + ' words, getting close to 25';
        } else if (words === 25) {
            cls = 'wc-perfect';
            msg = '25 words, perfect for print programme and magazines';
        } else {
            cls = 'wc-over';
            msg = words + ' words, over 25, print version will need shortening';
        }
        word_counter.attr('class', cls).text(msg);
    }

    copy_summary.bind('input propertychange', function() {
        update_character_count();
        update_word_count();
    });
    update_character_count();
    update_word_count();
  });

  // Break-even calculator
  (function () {
    'use strict';

    var FC_STANDARD = opts.breakevenFcStandardThreshold;
    var FC_MUSIC = opts.breakevenFcMusicThreshold;

    // Fixed costs (excluding artist deal, which is handled separately)
    var COST_IDS = ['be-hire', 'be-technical', 'be-accommodation', 'be-travel', 'be-food', 'be-other'];

    function num(id) { return parseFloat(document.getElementById(id).value) || 0; }
    function fmt(n) { return '£' + n.toFixed(2); }

    function calculate() {
        var otherCosts  = COST_IDS.reduce(function (s, id) { return s + num(id); }, 0);
        var capacity    = Math.max(1, Math.round(num('be-capacity')));
        var ticketPrice = num('be-ticket-price');
        var artistMG    = num('be-artist-mg');
        var artistPct   = Math.min(100, Math.max(0, num('be-artist-pct')));
        var barDrinks   = Math.max(0, num('be-bar-drinks'));   // avg drinks per person
        var barProfit   = Math.max(0, num('be-bar-profit'));   // avg profit per drink
        var barPerHead  = barDrinks * barProfit;               // bar revenue per attendee

        var output = document.getElementById('be-output');
        output.style.display = 'block';

        if (ticketPrice <= 0) {
            output.innerHTML = '<div class="alert alert-warning mb-0">Enter a ticket price to see results.</div>';
            return;
        }

        // Artist payment for N tickets sold
        function artistCost(tickets) {
            var gross = tickets * ticketPrice;
            if (artistPct === 0) return artistMG;
            if (artistMG === 0) return gross * artistPct / 100;
            return Math.max(artistMG, gross * artistPct / 100);
        }

        // Venue income for N tickets (box office share + bar)
        function venueIncome(tickets) {
            return tickets * ticketPrice - artistCost(tickets) + tickets * barPerHead;
        }

        // Profit for N tickets
        function vProfit(tickets) { return venueIncome(tickets) - otherCosts; }

        // --- Analytical break-even ---
        var breakEven;
        var effMGPerTicket  = ticketPrice + barPerHead;  // effective per-ticket when MG applies
        var effPctPerTicket = ticketPrice * (1 - artistPct / 100) + barPerHead; // when % applies

        if (artistPct === 0) {
            // Flat fee / MG only
            var costsMG = otherCosts + artistMG;
            breakEven = costsMG <= 0 ? 0 : Math.ceil(costsMG / effMGPerTicket);
        } else if (artistMG === 0) {
            // Pure % deal
            if (effPctPerTicket <= 0) {
                output.innerHTML = '<div class="alert alert-danger mb-0">Artist % leaves the venue with nothing per ticket sold.</div>';
                return;
            }
            breakEven = otherCosts <= 0 ? 0 : Math.ceil(otherCosts / effPctPerTicket);
        } else {
            // Whichever-greater: max(MG, N × price × pct%)
            if (effPctPerTicket <= 0) {
                output.innerHTML = '<div class="alert alert-danger mb-0">Artist % leaves the venue with nothing per ticket sold.</div>';
                return;
            }
            var nCrossover = artistMG / (ticketPrice * artistPct / 100);
            var nIfPct = otherCosts / effPctPerTicket;
            if (nIfPct >= nCrossover) {
                breakEven = Math.ceil(nIfPct);  // % deal active at break-even
            } else {
                var costsMG = otherCosts + artistMG;
                breakEven = costsMG <= 0 ? 0 : Math.ceil(costsMG / effMGPerTicket);
            }
        }

        var breakEvenPct = (breakEven / capacity * 100).toFixed(1);
        var impossible = breakEven > capacity;
        var html = '';

        // Summary banner
        html += '<div class="alert ' + (impossible ? 'alert-danger' : 'alert-success') + ' mb-2">';
        html += '<strong>Break-even: ' + breakEven + ' tickets (' + breakEvenPct + '% of ' + capacity + ' capacity)</strong>';
        if (impossible) { html += ' &mdash; costs cannot be covered even at a full room.'; }
        html += '</div>';

        // Finance Collective warning (on gross costs, not net of bar)
        var grossCosts = otherCosts + artistMG;
        if (grossCosts >= FC_MUSIC) {
            html += '<div class="alert alert-warning mb-2"><strong>Finance Collective required</strong> &mdash; costs (' + fmt(grossCosts) + ') exceed the £' + FC_MUSIC + ' music threshold.</div>';
        } else if (grossCosts >= FC_STANDARD) {
            html += '<div class="alert alert-warning mb-2"><strong>Finance Collective required</strong> &mdash; costs (' + fmt(grossCosts) + ') exceed the £' + FC_STANDARD + ' standard threshold.</div>';
        }

        // Fill scenarios table
        var showBar = barPerHead > 0;
        html += '<table class="table table-sm table-bordered mb-0"><thead class="thead-light"><tr>';
        html += '<th>Fill</th><th>Tickets</th><th>Box office</th>';
        if (showBar) { html += '<th>Bar revenue</th>'; }
        html += '<th>Profit / loss</th></tr></thead><tbody>';
        [0.25, 0.50, 0.75, 1.0].forEach(function (fillPct) {
            var tickets   = Math.round(capacity * fillPct);
            var boxOffice = tickets * ticketPrice - artistCost(tickets);
            var bar       = tickets * barPerHead;
            var profit    = vProfit(tickets);
            html += '<tr class="' + (profit >= 0 ? '' : 'table-danger') + '">';
            html += '<td>' + (fillPct * 100) + '%</td>';
            html += '<td>' + tickets + '</td>';
            html += '<td>' + fmt(boxOffice) + '</td>';
            if (showBar) { html += '<td>' + fmt(bar) + '</td>'; }
            html += '<td>' + (profit >= 0 ? '+' : '') + fmt(profit) + '</td>';
            html += '</tr>';
        });
        html += '</tbody></table>';

        output.innerHTML = html;
    }

    $(document).ready(function () {
        var $filmCollapse = $('#film-section-collapse');
        var $filmArrow = $('.film-section-arrow');
        $filmCollapse.on('show.bs.collapse', function () { $filmArrow.css('transform', 'rotate(90deg)'); });
        $filmCollapse.on('hide.bs.collapse', function () { $filmArrow.css('transform', 'rotate(0deg)'); });

        var $collapse = $('#be-collapse');
        var $arrow = $('.be-arrow');

        $collapse.on('show.bs.collapse', function () { $arrow.css('transform', 'rotate(90deg)'); });
        $collapse.on('hide.bs.collapse', function () { $arrow.css('transform', 'rotate(0deg)'); });

        $('#be-inputs input').on('input', calculate);
        $collapse.on('shown.bs.collapse', calculate);
    });
  }());

  $(document).ready(function () {
    var FIELD_TIPS = {
        'id_pre_title':                  'Optional text shown above/before the main title in public listings, e.g. “Cube Microplex presents”.',
        'id_name':                       'The main event title shown in the public programme and all listings.',
        'id_post_title':                 'Optional text shown below/after the main title in public listings, e.g. “with support from A Band”.',
        'id_tags':                       'Categories for this event. Affects which sections of the programme it appears in, and may exempt it from requiring terms. Bold tags are the most frequently used across all events.',
        'id_duration':                   'Running time of the event. Shown in public listings if set.',
        'id_pricing':                    'Pricing text shown to the public, e.g. “£5 Full / £3 Concession”. Leave blank if the event is free.',
        'id_ticket_link':                'URL for online ticket booking. Appears as a booking button in the public programme.',
        'id_trailer_url':                'Link to a trailer (YouTube, Vimeo, etc.). Appears as a “Watch trailer” link on the public event page.',
        'id_film_information':           'Screening details shown in public listings, e.g. “Dir: Jane Smith, 1990, USA, 95 mins, Cert: 15”.',
        'id_age_restriction':            'Under 18s must be accompanied by an adult at all events. Use this to flag family-friendly events (“All ages welcome”) or a minimum admission age (16+ / 18+ only).',
        'id_outside_hire':               'Tick if this event is run by an external organisation hiring the venue, not programmed by us. Affects internal reporting.',
        'id_hire_name':                  'Name of the person or organisation hiring the venue. Shown on the rota so everyone on shift knows who to liaise with.',
        'id_private':                    'When ticked, this event is hidden from the public website entirely — it won’t appear in any listing or be accessible via URL, even if showings are confirmed.',
        'id_notes':                      'Internal notes — never shown to the public. Use for booking contacts, reminders, or anything you need to track.',
        'id_cost_type':                  'The nature of the financial deal. Setting this unlocks structured cost fields and waives the minimum word-count check on Terms for confirmed events.',
        'id_cost_distributor':           'Distribution company, agent, or booker contact. Used for film licences and performer bookings.',
        'id_cost_flat_fee_gbp':          'Fixed upfront fee in pounds (e.g. a flat licence fee or guaranteed appearance fee).',
        'id_cost_fee_includes_vat':      'Tick if the fee above already includes VAT.',
        'id_cost_percentage_split':      'Percentage of net door takings paid to the distributor or performer.',
        'id_cost_minimum_guarantee_gbp': 'Guaranteed minimum payment regardless of door takings, in pounds.',
        'id_cost_total_gbp':             'Total agreed fee for the booking (performer / venue hire), in pounds. For private hires, records the income received.',
        'id_terms':                      'Booking or screening terms for this event. Must be filled in (minimum word count) before any showing can be confirmed, unless the event type exempts it or a cost type is set above.',
        'id_cost_rider_notes':           'Hospitality and rider requirements for the performer or hirer, e.g. food, drink, accommodation.',
        'id_cost_sound_engineer_name':   'Sound engineer name or contact, if one is booked for this event.',
        'id_cost_sound_engineer_fee_gbp': 'Sound engineer fee in pounds.',
        'id_cost_sound_engineer_paid_by': 'Who covers the sound engineer fee: the venue, the performer/act, or the hirer.',
        'id_copy':                       'The main event description shown in the public programme. Can be formatted with HTML (bold, links, etc.).',
        'id_copy_summary':               'Short plain-text description (ideally ≤25 words). Used in the print programme and brief online listings — separate from the full description above.',
        'id_media_file':                 'The event poster or promotional image shown in the public programme.',
        'id_alt_text':                   'Alternative text for screen readers and when images fail to load. Leave blank if no image is uploaded.',
        'id_credit':                     'Public attribution for the image — shown alongside the image on the event page, e.g. “Photo: Jane Smith”.',
        'id_approval_type':              'Record how this event was approved for the programme. Internal only.',
        'id_approved_at_meeting_date':   'Required when “Approved at meeting” is selected above.',
        'id_meeting_name':               'Optional. Name of the meeting, e.g. “Monday meeting”. Useful when minutes cover multiple meetings.',
        'id_meeting_minutes_url':        'Optional. Link to the meeting minutes (e.g. a shared doc or wiki page).',
        'id_programming_status':         'Internal status for the programming queue. “Active” is the default for normal events. Use “Draft” for ideas not yet ready to propose, “Proposed” to flag for Monday meeting discussion.',
        'id_programming_notes':          'Free text visible to all logged-in users. Use for meeting decisions, approval conditions, messages to the proposer, or tech/AV requirements.',
    };

    // Show/hide hire_name based on the outside_hire checkbox.
    (function () {
        var hireNameDiv = document.getElementById('div_id_hire_name');
        var outsideHireBox = document.getElementById('id_outside_hire');

        function applyHireNameVisibility() {
            if (hireNameDiv) {
                hireNameDiv.style.display = outsideHireBox && outsideHireBox.checked ? '' : 'none';
            }
        }

        if (outsideHireBox) {
            applyHireNameVisibility();
            outsideHireBox.addEventListener('change', applyHireNameVisibility);
        }
    }());

    // Show/hide the three meeting-specific fields based on approval_type.
    (function () {
        var MEETING_FIELD_IDS = ['div_id_approved_at_meeting_date', 'div_id_meeting_name', 'div_id_meeting_minutes_url'];

        function applyApprovalVisibility(val) {
            var show = val === 'meeting';
            MEETING_FIELD_IDS.forEach(function (id) {
                var el = document.getElementById(id);
                if (el) { el.style.display = show ? '' : 'none'; }
            });
        }

        var sel = document.getElementById('id_approval_type');
        if (sel) {
            applyApprovalVisibility(sel.value);
            sel.addEventListener('change', function () { applyApprovalVisibility(this.value); });
        }
    }());

    if (opts.structuredCostTermsEnabled) {
    // Structured cost terms (9.54) — show/hide sub-fields, swap labels, and set
    // contextual placeholder text on Terms based on cost_type.
    (function () {
        var FILM_FIELDS      = ['div_id_cost_distributor', 'div_id_cost_flat_fee_gbp', 'div_id_cost_fee_includes_vat',
                                'div_id_cost_percentage_split', 'div_id_cost_minimum_guarantee_gbp'];
        var PERFORMER_FIELDS = ['div_id_cost_distributor', 'div_id_cost_flat_fee_gbp', 'div_id_cost_fee_includes_vat',
                                'div_id_cost_total_gbp',
                                'div_id_cost_rider_notes', 'div_id_cost_sound_engineer_name',
                                'div_id_cost_sound_engineer_fee_gbp', 'div_id_cost_sound_engineer_paid_by'];
        var HIRE_FIELDS      = ['div_id_cost_distributor', 'div_id_cost_flat_fee_gbp', 'div_id_cost_fee_includes_vat',
                                'div_id_cost_total_gbp',
                                'div_id_cost_rider_notes', 'div_id_cost_sound_engineer_name',
                                'div_id_cost_sound_engineer_fee_gbp', 'div_id_cost_sound_engineer_paid_by'];
        var ALL_COST_FIELDS  = ['div_id_cost_distributor', 'div_id_cost_flat_fee_gbp', 'div_id_cost_fee_includes_vat',
                                'div_id_cost_percentage_split', 'div_id_cost_minimum_guarantee_gbp', 'div_id_cost_total_gbp',
                                'div_id_cost_rider_notes', 'div_id_cost_sound_engineer_name',
                                'div_id_cost_sound_engineer_fee_gbp', 'div_id_cost_sound_engineer_paid_by'];

        // field id → { label text, placeholder } per cost_type
        var LABELS = {
            'id_cost_distributor': {
                'film_license':  'Distributor',
                'performer_fee': 'Performer / booker',
                'venue_hire':    'Hirer / contact',
            },
            'id_cost_percentage_split': {
                'film_license':  '% of net door to distributor',
                'performer_fee': '% of door to performer',
            },
            'id_cost_total_gbp': {
                'film_license':  'Total cost (£)',
                'performer_fee': 'Total agreed fee (£)',
                'venue_hire':    'Total income (£)',
            },
        };
        var DEFAULT_LABELS = {
            'id_cost_distributor':    'Distributor / booker',
            'id_cost_percentage_split': '% split to distributor',
            'id_cost_total_gbp':       'Total cost (£)',
        };
        var TERMS_PLACEHOLDERS = {
            'film_license':  'e.g. Exclusivity window until [date]; subtitles required; format restrictions.',
            'performer_fee': 'e.g. Door deal: costs off the top (PRS, bar cut), then 70/30 split. Support act £50 from venue.',
            'venue_hire':    'e.g. Hire includes main hall and PA. Hirer sets up and breaks down. Noise curfew 11pm.',
        };
        var DEFAULT_TERMS_PLACEHOLDER = opts.defaultTermsPlaceholder;

        function applyFiledVisibility() {
            var sel = document.getElementById('id_cost_type');
            if (!sel) { return; }
            var v = sel.value;
            var show = [];
            if (v === 'film_license')   { show = FILM_FIELDS; }
            else if (v === 'performer_fee') { show = PERFORMER_FIELDS; }
            else if (v === 'venue_hire')    { show = HIRE_FIELDS; }

            ALL_COST_FIELDS.forEach(function (id) {
                var el = document.getElementById(id);
                if (el) { el.style.display = show.indexOf(id) !== -1 ? '' : 'none'; }
            });

            // Swap labels
            Object.keys(LABELS).forEach(function (fieldId) {
                var labelEl = document.querySelector('label[for="' + fieldId + '"]');
                if (!labelEl) { return; }
                var textNode = Array.from(labelEl.childNodes).find(function (n) { return n.nodeType === 3; });
                var newText = (LABELS[fieldId][v] || DEFAULT_LABELS[fieldId] || '') + ':';
                if (textNode) { textNode.textContent = newText; }
            });

            // Update terms placeholder
            var termsEl = document.getElementById('id_terms');
            if (termsEl) {
                termsEl.placeholder = TERMS_PLACEHOLDERS[v] || DEFAULT_TERMS_PLACEHOLDER;
            }
        }

        var costSel = document.getElementById('id_cost_type');
        if (costSel) {
            applyFiledVisibility();
            costSel.addEventListener('change', applyFiledVisibility);
        }
    }());
    }

    $.each(FIELD_TIPS, function (fieldId, tipText) {
        var $label = $('label[for="' + fieldId + '"]');
        if (!$label.length) {
            // Some widgets (e.g. CheckboxSelectMultiple) don't set for= on their label;
            // fall back to the first label inside the crispy wrapper div.
            $label = $('#div_' + fieldId + ' > label').first();
        }
        if ($label.length) {
            $label.append(
                $('<span>').addClass('field-tip')
                    .attr({'data-bs-toggle': 'tooltip', 'data-bs-placement': 'right', 'title': tipText})
                    .text('ⓘ')
            );
        }
    });

    document.querySelectorAll('[data-bs-toggle="tooltip"]').forEach(function(el) { new bootstrap.Tooltip(el); });

    if (opts.ticketLinkGuidanceHtml) {
    // Ticket link setup guide — injected after the ticket_link field.
    (function () {
        var ticketDiv = document.getElementById('div_id_ticket_link');
        if (!ticketDiv) { return; }
        var guideUrl = opts.filmProgrammingGuideUrl;
        var guideLink = guideUrl ? ' <a href="' + guideUrl + '" target="_blank" rel="noopener noreferrer">Full programming guide →</a>' : '';
        var guidanceBody = opts.ticketLinkGuidanceHtml;
        var html = '<div class="mb-3 border rounded" id="ticket-link-guide">'
            + '<div class="d-flex align-items-center px-3 py-2" style="cursor:pointer;" id="ticket-link-guide-toggle" onclick="var b=document.getElementById(\'ticket-link-guide-body\');var arr=this.querySelector(\'.ts-arrow\');b.style.display=b.style.display===\'none\'?\'\':\'none\';arr.textContent=b.style.display===\'none\'?\'▶\':\'▼\';">'
            + '<span class="ts-arrow me-2">▶</span>'
            + '<strong>Ticket link setup guide</strong>'
            + '<span class="text-muted small ms-2">(expand for a quick checklist)</span>'
            + '</div>'
            + '<div id="ticket-link-guide-body" style="display:none;" class="px-3 pb-3 small">'
            + guidanceBody
            + guideLink
            + '</div>'
            + '</div>';
        ticketDiv.insertAdjacentHTML('afterend', html);
    }());
    }

    if (opts.tagDescriptionsJson) {
    /* Tag pill tooltips — show "when to use" guidance on each tag label */
    (function() {
        var tagDesc = opts.tagDescriptionsJson;
        document.querySelectorAll('.tag-pill input[type=checkbox]').forEach(function(cb) {
            var desc = tagDesc[cb.value];
            if (desc) {
                var label = cb.closest('label');
                label.setAttribute('data-bs-toggle', 'tooltip');
                label.setAttribute('data-bs-placement', 'top');
                label.setAttribute('title', desc);
                var tip = new bootstrap.Tooltip(label, { trigger: 'hover' });
                label.addEventListener('click', function() { tip.hide(); });
            }
        });
    }());
    }

    if (opts.top5TagPks) {
    /* Bold the top-5 most-used tags in the pill list. */
    (function() {
        var top5 = opts.top5TagPks;
        if (!top5.length) return;
        document.querySelectorAll('.tag-pill-select label.tag-pill').forEach(function(label) {
            var pk = parseInt(label.querySelector('input').value, 10);
            if (top5.indexOf(pk) !== -1) { label.classList.add('tag-pill--common'); }
        });
    }());
    }

    // Poster generation AJAX
    (function() {
        var generateBtn = document.getElementById('generate-poster-btn');
        var removeBtn = document.getElementById('remove-generated-btn');
        var fileInput = document.getElementById('id_media_file');
        var fileGroup = document.getElementById('media_file_group');
        var previewDiv = document.getElementById('generated-preview');
        var previewImg = document.getElementById('generated-preview-img');
        var filenameSpan = document.getElementById('generated-filename');
        var hiddenInput = document.getElementById('generated_media_id');
        var colourInput = document.getElementById('poster-accent-colour');
        var csrftoken = document.querySelector('[name=csrfmiddlewaretoken]').value;

        function showPreview(data) {
            hiddenInput.value = data.media_id;
            previewImg.src = data.url;
            filenameSpan.textContent = data.filename;
            fileGroup.style.display = 'none';
            previewDiv.style.display = 'flex';
        }

        function removePreview() {
            hiddenInput.value = '';
            previewImg.src = '';
            filenameSpan.textContent = '';
            previewDiv.style.display = 'none';
            fileGroup.style.display = 'flex';
            // Note: we don't delete the MediaItem server-side; it just won't be attached to the event
        }

        function generatePoster() {
            var url = opts.generatePosterUrl;
            var colour = colourInput ? colourInput.value : null;

            generateBtn.disabled = true;
            var originalText = generateBtn.innerHTML;
            generateBtn.innerHTML = '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span> Generating...';

            var formData = new FormData();
            if (colour) {
                formData.append('colour', colour);
            }

            fetch(url, {
                method: 'POST',
                headers: {
                    'X-CSRFToken': csrftoken,
                    'X-Requested-With': 'XMLHttpRequest'
                },
                body: formData
            })
            .then(function(response) {
                if (!response.ok) {
                    throw new Error('HTTP ' + response.status);
                }
                return response.json();
            })
            .then(function(data) {
                if (data.success) {
                    showPreview(data);
                } else {
                    alert('Failed to generate poster: ' + (data.error || 'Unknown error'));
                }
            })
            .catch(function(err) {
                alert('Error generating poster: ' + err.message);
            })
            .finally(function() {
                generateBtn.disabled = false;
                generateBtn.innerHTML = '<span aria-hidden="true">&#x1F3A8;</span> Generate poster';
            });
        }

        if (generateBtn) generateBtn.addEventListener('click', generatePoster);
        if (removeBtn) removeBtn.addEventListener('click', removePreview);
    }());
  });

  // Crop tool and letterbox bars (unified).
  document.addEventListener('DOMContentLoaded', function () {
    var CROP_ASPECT  = opts.cropAspect;
    var ACCENT_COLOUR = opts.accentColour;

    var fileInput       = document.getElementById('id_media_file');
    var cropRow         = document.getElementById('crop-tool-row');
    var cropImg         = document.getElementById('crop-tool-img');
    var inputCropX      = document.getElementById('id_crop_x');
    var inputCropY      = document.getElementById('id_crop_y');
    var inputCropW      = document.getElementById('id_crop_w');
    var inputCropH      = document.getElementById('id_crop_h');
    var barsToggle      = document.getElementById('bars-toggle');
    var barsPanel       = document.getElementById('bars-panel');
    var colourInput     = document.getElementById('id_bar_colour');   // hidden form field
    var barColourPicker = document.getElementById('bar-colour-picker'); // cosmetic picker
    var transparentBtn  = document.getElementById('bar-transparent-btn');
    var swatchContainer = document.getElementById('bar-colour-swatches');
    var cropper         = null;
    var lastImageBounds = null; // image content area within the padded canvas
    // URL of the raw (un-padded) image.
    var rawImageUrl = cropImg ? (cropImg.getAttribute('src') || '') : '';

    // --- canvas padding ---

    // Pad imgEl to CROP_ASPECT. If hexColour is set, fills bars with that colour;
    // otherwise draws a checkerboard to indicate the bars will be transparent.
    // Returns null if the image is already close enough to the target ratio.
    function buildPaddedResult(imgEl, hexColour) {
        var origW = imgEl.naturalWidth;
        var origH = imgEl.naturalHeight;
        if (!origW || !origH) return null;
        var actualRatio = origW / origH;
        if (Math.abs(actualRatio - CROP_ASPECT) < 0.02) return null;

        var canvasW, canvasH, pasteX, pasteY;
        if (actualRatio > CROP_ASPECT) {
            canvasW = origW;
            canvasH = Math.round(origW / CROP_ASPECT);
            pasteX  = 0;
            pasteY  = Math.round((canvasH - origH) / 2);
        } else {
            canvasH = origH;
            canvasW = Math.round(origH * CROP_ASPECT);
            pasteX  = Math.round((canvasW - origW) / 2);
            pasteY  = 0;
        }

        var canvas = document.createElement('canvas');
        canvas.width  = canvasW;
        canvas.height = canvasH;
        var ctx = canvas.getContext('2d');
        if (hexColour) {
            ctx.fillStyle = hexColour;
            ctx.fillRect(0, 0, canvasW, canvasH);
        } else {
            // Checkerboard to indicate the bars will be transparent in the saved thumbnail.
            var sz = Math.max(8, Math.round(Math.min(canvasW, canvasH) / 20));
            for (var cy = 0; cy < canvasH; cy += sz) {
                for (var cx = 0; cx < canvasW; cx += sz) {
                    ctx.fillStyle = ((Math.floor(cx/sz) + Math.floor(cy/sz)) % 2 === 0) ? '#cccccc' : '#ffffff';
                    ctx.fillRect(cx, cy, sz, sz);
                }
            }
        }
        ctx.drawImage(imgEl, pasteX, pasteY);

        lastImageBounds = {
            cx: pasteX / canvasW,
            cy: pasteY / canvasH,
            cw: origW  / canvasW,
            ch: origH  / canvasH
        };
        return { dataUrl: canvas.toDataURL('image/jpeg', 0.9), imageBounds: lastImageBounds };
    }

    // --- crop helpers ---

    function setCropData(nx, ny, nw, nh) {
        if (!cropper) return;
        var imgData = cropper.getImageData();
        cropper.setData({
            x:      nx * imgData.naturalWidth,
            y:      ny * imgData.naturalHeight,
            width:  nw * imgData.naturalWidth,
            height: nh * imgData.naturalHeight
        });
    }

    function restoreExistingCrop() {
        if (!inputCropX) return;
        var cx = parseFloat(inputCropX.value);
        var cy = parseFloat(inputCropY.value);
        var cw = parseFloat(inputCropW.value);
        var ch = parseFloat(inputCropH.value);
        if (!isNaN(cx) && cw > 0 && ch > 0) { setCropData(cx, cy, cw, ch); }
    }

    function saveCropToInputs() {
        if (!cropper || !inputCropX) return;
        var data    = cropper.getData(true);
        var imgData = cropper.getImageData();
        if (imgData.naturalWidth && imgData.naturalHeight) {
            inputCropX.value = (data.x      / imgData.naturalWidth ).toFixed(6);
            inputCropY.value = (data.y      / imgData.naturalHeight).toFixed(6);
            inputCropW.value = (data.width  / imgData.naturalWidth ).toFixed(6);
            inputCropH.value = (data.height / imgData.naturalHeight).toFixed(6);
        }
    }

    // doRestoreCrop: restore saved coords; defaultCrop: normalised {cx,cy,cw,ch} to set instead.
    function initCropper(doRestoreCrop, defaultCrop) {
        if (!cropImg || !window.Cropper) return;
        if (cropper) { cropper.destroy(); }
        cropper = new Cropper(cropImg, {
            aspectRatio: CROP_ASPECT,
            viewMode: 1,
            autoCropArea: 1,
            zoomable: false,
            scalable: false,
            rotatable: false,
            ready: function() {
                if (doRestoreCrop) {
                    restoreExistingCrop();
                } else if (defaultCrop) {
                    setCropData(defaultCrop.cx, defaultCrop.cy, defaultCrop.cw, defaultCrop.ch);
                }
            }
        });
    }

    function showCropTool(url, doRestoreCrop, defaultCrop) {
        if (!cropRow || !url) return;
        cropRow.style.display = '';
        cropImg.src = url;
        initCropper(doRestoreCrop || false, defaultCrop || null);
    }

    // Rebuild the cropper preview. The padded canvas is always shown (transparent
    // checkerboard or chosen colour in the bar areas).
    //
    // restoreSavedCrop = true  → keep the current hidden-input crop values
    // restoreSavedCrop = false → clear them; default crop depends on bars toggle:
    //   bars ON  → full canvas (0 0 1 1) so bars are visible
    //   bars OFF → imageBounds (just the image content, bars cropped out)
    function refreshCropper(restoreSavedCrop) {
        if (!rawImageUrl) return;
        var colour = (colourInput && colourInput.value) ? colourInput.value : '';
        if (!restoreSavedCrop && inputCropX) {
            inputCropX.value = ''; inputCropY.value = ''; inputCropW.value = ''; inputCropH.value = '';
        }
        var img = new Image();
        img.onload = function() {
            var result = buildPaddedResult(img, colour);
            if (result) {
                var hasSavedCrop = inputCropX && inputCropX.value;
                if (restoreSavedCrop && hasSavedCrop) {
                    showCropTool(result.dataUrl, true, null);
                } else if (barsToggle && barsToggle.checked) {
                    showCropTool(result.dataUrl, false, {cx:0, cy:0, cw:1, ch:1});
                } else {
                    showCropTool(result.dataUrl, false, result.imageBounds);
                }
            } else {
                lastImageBounds = null;
                showCropTool(rawImageUrl, restoreSavedCrop, null);
            }
        };
        img.src = rawImageUrl;
    }

    // Save on form submit.
    var form = cropRow ? cropRow.closest('form') : null;
    if (form) { form.addEventListener('submit', saveCropToInputs); }

    // --- file input ---

    if (fileInput) {
        fileInput.addEventListener('change', function() {
            var file = fileInput.files && fileInput.files[0];
            if (!file || !file.type.startsWith('image/')) return;
            rawImageUrl = URL.createObjectURL(file);
            var img = new Image();
            img.onload = function() {
                showSwatches(extractDominantColours(img, 5));
            };
            img.src = rawImageUrl;
            refreshCropper(false);
        });
    }

    // --- bars toggle and colour controls ---

    if (barsToggle && barsPanel) {
        barsToggle.addEventListener('change', function() {
            barsPanel.style.display = barsToggle.checked ? '' : 'none';
            if (barsToggle.checked) {
                // Expand crop to full canvas so bars are included.
                if (cropper && lastImageBounds) { setCropData(0, 0, 1, 1); }
                else { refreshCropper(false); }
            } else {
                // Contract crop back to image content; clear any colour.
                if (colourInput) colourInput.value = '';
                if (barColourPicker) barColourPicker.value = '#000000';
                if (cropper && lastImageBounds) {
                    setCropData(lastImageBounds.cx, lastImageBounds.cy, lastImageBounds.cw, lastImageBounds.ch);
                } else { refreshCropper(false); }
            }
        });

        // Transparent swatch: clear the colour, preview updates to checkerboard.
        if (transparentBtn) {
            transparentBtn.addEventListener('click', function() {
                if (colourInput) colourInput.value = '';
                if (barColourPicker) barColourPicker.value = '#000000';
                if (rawImageUrl) refreshCropper(true);
            });
        }

        // Cosmetic colour picker: sync to hidden form field.
        if (barColourPicker) {
            barColourPicker.addEventListener('input', function() {
                if (colourInput) colourInput.value = barColourPicker.value;
                if (rawImageUrl) refreshCropper(true);
            });
        }

        // Initialise toggle and panel from existing bar_colour value.
        if (colourInput && colourInput.value) {
            barsToggle.checked = true;
            barsPanel.style.display = '';
            if (barColourPicker) barColourPicker.value = colourInput.value;
        } else {
            barsPanel.style.display = 'none';
        }
    }

    // --- page load ---

    // Show brand colour swatches immediately (no image needed).
    showSwatches([]);
    if (rawImageUrl) {
        // Enrich swatches with dominant colours from the existing image.
        var preImg = new Image();
        preImg.onload = function() { showSwatches(extractDominantColours(preImg, 5)); };
        preImg.src = rawImageUrl;
        // Show crop tool, restoring any previously saved crop.
        refreshCropper(true);
    }

    // --- colour helpers ---

    function rgbToHex(r, g, b) {
        return '#' + [r, g, b].map(function(x) { return x.toString(16).padStart(2, '0'); }).join('');
    }

    function hexToRgb(hex) {
        var h = hex.replace('#', '');
        return [parseInt(h.slice(0,2),16), parseInt(h.slice(2,4),16), parseInt(h.slice(4,6),16)];
    }

    // Convert RGB to HSL (h: 0-360, s/l: 0-1).
    function rgbToHsl(r, g, b) {
        r /= 255; g /= 255; b /= 255;
        var max = Math.max(r,g,b), min = Math.min(r,g,b), d = max - min;
        var h = 0, s = 0, l = (max + min) / 2;
        if (d) {
            s = d / (1 - Math.abs(2 * l - 1));
            h = max === r ? ((g - b) / d + (g < b ? 6 : 0)) / 6
              : max === g ? ((b - r) / d + 2) / 6
              :              ((r - g) / d + 4) / 6;
        }
        return [h * 360, s, l];
    }

    function hslToRgb(h, s, l) {
        h /= 360;
        var a = s * Math.min(l, 1 - l);
        function f(n) {
            var k = (n + h * 12) % 12;
            return l - a * Math.max(Math.min(k - 3, 9 - k, 1), -1);
        }
        return [Math.round(f(0)*255), Math.round(f(8)*255), Math.round(f(4)*255)];
    }

    // Generate accent-related bar colour suggestions: the accent itself, its
    // complementary (hue +180°), a darkened version, and near-black/near-white.
    function accentSuggestions(hexColour) {
        if (!hexColour || hexColour.length < 7) return [];
        try {
            var rgb  = hexToRgb(hexColour);
            var hsl  = rgbToHsl(rgb[0], rgb[1], rgb[2]);
            var h = hsl[0], s = hsl[1], l = hsl[2];
            // Accent itself (if not too light for a bar).
            var accent = hexColour;
            // Complementary: opposite hue, same saturation and lightness.
            var compRgb = hslToRgb((h + 180) % 360, s, l);
            var comp = rgbToHex(compRgb[0], compRgb[1], compRgb[2]);
            // Darkened accent: same hue/sat, lightness 15%.
            var darkRgb = hslToRgb(h, s, 0.15);
            var dark = rgbToHex(darkRgb[0], darkRgb[1], darkRgb[2]);
            // Near-black and near-white for neutral coverage.
            return [accent, comp, dark, '#111111', '#f5f5f5'];
        } catch (e) { return []; }
    }

    function extractDominantColours(imgEl, n) {
        var maxDim = 60;
        var scale = Math.min(maxDim / imgEl.naturalWidth, maxDim / imgEl.naturalHeight, 1);
        var cw = Math.max(1, Math.round(imgEl.naturalWidth  * scale));
        var ch = Math.max(1, Math.round(imgEl.naturalHeight * scale));
        var canvas = document.createElement('canvas');
        canvas.width = cw; canvas.height = ch;
        var ctx = canvas.getContext('2d');
        ctx.drawImage(imgEl, 0, 0, cw, ch);
        var data = ctx.getImageData(0, 0, cw, ch).data;
        var buckets = {};
        for (var i = 0; i < data.length; i += 4) {
            var r = data[i] >> 3, g = data[i+1] >> 3, b = data[i+2] >> 3;
            var key = (r << 10) | (g << 5) | b;
            if (!buckets[key]) buckets[key] = {rs:0, gs:0, bs:0, n:0};
            buckets[key].rs += data[i]; buckets[key].gs += data[i+1]; buckets[key].bs += data[i+2]; buckets[key].n++;
        }
        return Object.values(buckets)
            .sort(function(a, b) { return b.n - a.n; })
            .slice(0, n)
            .map(function(bk) { return rgbToHex(Math.round(bk.rs/bk.n), Math.round(bk.gs/bk.n), Math.round(bk.bs/bk.n)); });
    }

    function makeSwatch(hex, label) {
        var btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'bar-colour-swatch btn btn-sm';
        btn.style.cssText = 'width:28px;height:28px;padding:0;background:' + hex + ';border:2px solid rgba(0,0,0,0.2);border-radius:4px;';
        btn.title = (label ? label + ' ' : '') + hex;
        btn.setAttribute('aria-label', (label || 'Use colour') + ' ' + hex);
        btn.addEventListener('click', function() {
            if (colourInput) colourInput.value = hex;
            if (barColourPicker) barColourPicker.value = hex;
            if (rawImageUrl) refreshCropper(true);
        });
        return btn;
    }

    // imageColours: from dominant extraction; shown after a divider from brand colours.
    function showSwatches(imageColours) {
        if (!swatchContainer) return;
        swatchContainer.querySelectorAll('.bar-colour-swatch, .swatch-divider').forEach(function(el) { el.remove(); });

        var brandColours = accentSuggestions(ACCENT_COLOUR);
        brandColours.forEach(function(hex) { swatchContainer.appendChild(makeSwatch(hex)); });

        if (imageColours && imageColours.length) {
            var div = document.createElement('span');
            div.className = 'swatch-divider';
            div.style.cssText = 'align-self:center;color:#999;font-size:0.75em;margin:0 2px;';
            div.textContent = '|';
            swatchContainer.appendChild(div);
            imageColours.forEach(function(hex) { swatchContainer.appendChild(makeSwatch(hex, 'From image:')); });
        }

        swatchContainer.style.display = 'flex';
    }
  });

  // OMDb film search / link.
  (function() {
    var SEARCH_URL = opts.omdbSearchUrl;
    var LINK_URL   = opts.linkFilmUrl;

    document.addEventListener('DOMContentLoaded', function() {
      var filmSection   = document.getElementById('film-section');
      var lastSuggested = (filmSection && filmSection.dataset.suggested) || '';

      /* ---- reposition film section immediately after film_information row ---- */
      var fiField = document.getElementById('id_film_information');
      if (fiField && filmSection) {
        var fiRow = fiField.closest('.mb-3');
        if (fiRow && fiRow.parentNode) {
          fiRow.parentNode.insertBefore(filmSection, fiRow.nextSibling);
        }
      }

      /* ---- helpers ---- */
      function getCsrf() {
        var el = document.querySelector('[name=csrfmiddlewaretoken]');
        return el ? el.value : '';
      }

      function fillManualForm(film) {
        var set = function(id, val) { var el = document.getElementById(id); if (el) el.value = val || ''; };
        set('film-manual-title', film.title);
        set('film-manual-year', film.year);
        set('film-manual-director', film.director);
        set('film-manual-runtime', film.runtime_minutes);
        set('film-manual-countries', film.countries);
        set('film-manual-languages', film.languages);
        var typeEl = document.getElementById('film-manual-type');
        if (typeEl) typeEl.value = film.media_type || 'film';
      }

      function showLinked(film) {
        var linked     = document.getElementById('film-linked');
        var searchWrap = document.getElementById('film-search-wrap');
        var manualWrap = document.getElementById('film-manual-wrap');

        document.getElementById('film-title').textContent =
          film.title + (film.year ? ' (' + film.year + ')' : '');

        var sourceBadge = document.getElementById('film-source-badge');
        if (sourceBadge) {
          if (film.imdb_id) {
            sourceBadge.textContent = 'via OMDb';
            sourceBadge.className = 'badge ms-1 text-bg-info';
          } else {
            sourceBadge.textContent = 'manually entered';
            sourceBadge.className = 'badge ms-1 text-bg-secondary';
          }
          sourceBadge.style.fontSize = '0.7em';
          sourceBadge.style.fontWeight = 'normal';
        }

        var editBtn = document.getElementById('film-edit-btn');
        if (editBtn) editBtn.style.display = film.imdb_id ? 'none' : '';

        var metaParts = [];
        if (film.director) metaParts.push('Dir. ' + film.director);
        if (film.runtime_minutes) metaParts.push(film.runtime_minutes + ' mins');
        if (film.countries) metaParts.push(film.countries);
        document.getElementById('film-meta').textContent = metaParts.join(' · ');

        var poster = document.getElementById('film-poster-sm');
        if (film.poster_url || film.poster_url_sm) {
          poster.src = film.poster_url || film.poster_url_sm;
          poster.style.display = '';
        } else {
          poster.style.display = 'none';
        }

        var linksEl = document.getElementById('film-links');
        linksEl.innerHTML = '';
        if (film.imdb_url) {
          var a = document.createElement('a');
          a.href = film.imdb_url; a.target = '_blank';
          a.className = 'text-muted small'; a.textContent = 'IMDB ↗';
          linksEl.appendChild(a);
        }
        var certTemplate = opts.certificateLookupUrl;
        if (certTemplate && film.title) {
          var certUrl = certTemplate
            .replace('{title}', encodeURIComponent(film.title))
            .replace('{year}', encodeURIComponent(film.year || ''));
          var certLink = document.createElement('a');
          certLink.href = certUrl; certLink.target = '_blank'; certLink.rel = 'noopener noreferrer';
          certLink.className = 'text-muted small ms-2'; certLink.textContent = 'Check cert ↗';
          linksEl.appendChild(certLink);
        }

        if (linked) linked.style.display = '';
        if (searchWrap) searchWrap.style.display = 'none';
        if (manualWrap) manualWrap.style.display = 'none';
        var fc = document.getElementById('film-section-collapse');
        if (fc && !fc.classList.contains('show')) {
          new bootstrap.Collapse(fc, {toggle: false}).show();
        }

        /* pre-fill manual form so programmer only needs to fix one field */
        fillManualForm(film);
      }

      function suggestFilmInfo(suggested) {
        lastSuggested = suggested || '';
        var fi = document.getElementById('id_film_information');
        if (fi && !fi.value.trim()) fi.value = suggested;
      }

      /* ---- apply suggestion button ---- */
      var applyInfoBtn = document.getElementById('film-apply-info-btn');
      if (applyInfoBtn) {
        applyInfoBtn.addEventListener('click', function() {
          var fi = document.getElementById('id_film_information');
          if (fi && lastSuggested) fi.value = lastSuggested;
        });
      }

      /* ---- OMDb search ---- */
      var searchInput   = document.getElementById('film-search-input');
      var searchResults = document.getElementById('film-search-results');
      var searchTimer   = null;

      /* pre-fill search from event title when section expands with no film linked */
      var filmCollapse = document.getElementById('film-section-collapse');
      if (filmCollapse && searchInput) {
        filmCollapse.addEventListener('show.bs.collapse', function() {
          var linked   = document.getElementById('film-linked');
          var isLinked = linked && linked.style.display !== 'none';
          if (!isLinked && !searchInput.value.trim()) {
            var nameField = document.getElementById('id_name');
            if (nameField && nameField.value.trim()) {
              searchInput.value = nameField.value.trim();
              searchInput.dispatchEvent(new Event('input'));
            }
          }
        });
      }

      /* "Use event title" button */
      var useTitleBtn = document.getElementById('film-use-title-btn');
      if (useTitleBtn && searchInput) {
        useTitleBtn.addEventListener('click', function() {
          searchInput.value = useTitleBtn.dataset.title || '';
          searchInput.dispatchEvent(new Event('input'));
          searchInput.focus();
        });
      }

      var searchError = document.getElementById('film-search-error');

      if (searchInput) {
        searchInput.addEventListener('input', function() {
          clearTimeout(searchTimer);
          var q = searchInput.value.trim();
          if (!q) { searchResults.style.display = 'none'; return; }
          searchTimer = setTimeout(function() {
            fetch(SEARCH_URL + '?q=' + encodeURIComponent(q), {
              headers: {'X-Requested-With': 'XMLHttpRequest'}
            })
            .then(function(r) { return r.json(); })
            .then(function(data) {
              searchResults.innerHTML = '';
              if (!Array.isArray(data)) {
                // Search failed server-side (rate limit, bad key, etc.) — show why.
                searchResults.style.display = 'none';
                if (searchError) {
                  searchError.textContent = data.error || 'OMDb search failed.';
                  searchError.style.display = '';
                }
                return;
              }
              if (searchError) searchError.style.display = 'none';
              if (!data.length) {
                searchResults.style.display = 'none'; return;
              }
              data.forEach(function(item) {
                var btn = document.createElement('button');
                btn.type = 'button';
                btn.className = 'list-group-item list-group-item-action d-flex gap-2 align-items-center py-1';
                var img = item.poster_url
                  ? '<img src="' + item.poster_url + '" width="32" style="border-radius:2px;flex-shrink:0" alt="">'
                  : '<span style="width:32px;flex-shrink:0"></span>';
                var badge = item.media_type === 'tv'
                  ? '<span class="badge text-bg-secondary ms-1">TV</span>' : '';
                btn.innerHTML = img + '<span>' + item.title + badge +
                  '<br><small class="text-muted">' + (item.year || '') +
                  (item.director ? ' · ' + item.director : '') + '</small></span>';
                btn.addEventListener('click', function() { linkFilm(item.imdb_id, item.media_type); });
                searchResults.appendChild(btn);
              });
              searchResults.style.display = '';
            })
            .catch(function() {
              searchResults.style.display = 'none';
              if (searchError) {
                searchError.textContent = 'OMDb search failed.';
                searchError.style.display = '';
              }
            });
          }, 300);
        });
      }

      function linkFilm(imdbId, mediaType) {
        var formData = new FormData();
        formData.append('csrfmiddlewaretoken', getCsrf());
        formData.append('imdb_id', imdbId);
        formData.append('media_type', mediaType);
        fetch(LINK_URL, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
        .then(function(r) { return r.json(); })
        .then(function(data) {
          if (data.success) {
            showLinked(data.film);
            suggestFilmInfo(data.suggested_film_information);
            if (searchResults) { searchResults.innerHTML = ''; searchResults.style.display = 'none'; }
            if (searchInput) searchInput.value = '';
            if (searchError) searchError.style.display = 'none';
          } else if (searchError) {
            searchError.textContent = data.error || 'Could not link this film.';
            searchError.style.display = '';
          }
        });
      }

      /* ---- unlink ---- */
      var unlinkBtn = document.getElementById('film-unlink-btn');
      if (unlinkBtn) {
        unlinkBtn.addEventListener('click', function() {
          var formData = new FormData();
          formData.append('csrfmiddlewaretoken', getCsrf());
          fetch(unlinkBtn.dataset.url, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.success) {
              var linked     = document.getElementById('film-linked');
              var searchWrap = document.getElementById('film-search-wrap');
              var manualWrap = document.getElementById('film-manual-wrap');
              if (linked) linked.style.display = 'none';
              if (searchWrap) searchWrap.style.display = '';
              else if (manualWrap) manualWrap.style.display = '';
            }
          });
        });
      }

      /* ---- pre-fill manual form from server-side film data on page load ---- */
      var initialFilmData = filmSection && filmSection.dataset.film;
      if (initialFilmData && initialFilmData !== 'null') {
        try { fillManualForm(JSON.parse(initialFilmData)); } catch(e) {}
      }

      /* ---- edit button for manually-entered films ---- */
      var editBtn = document.getElementById('film-edit-btn');
      if (editBtn) {
        editBtn.addEventListener('click', function() {
          var linked     = document.getElementById('film-linked');
          var manualWrap = document.getElementById('film-manual-wrap');
          var searchWrap = document.getElementById('film-search-wrap');
          if (linked) linked.style.display = 'none';
          if (searchWrap) searchWrap.style.display = 'none';
          if (manualWrap) manualWrap.style.display = '';
          var submitBtn = document.getElementById('film-manual-submit');
          if (submitBtn) submitBtn.textContent = 'Save changes';
        });
      }

      /* ---- manual toggle ---- */
      var manualToggle = document.getElementById('film-manual-toggle');
      var searchToggle = document.getElementById('film-search-toggle');
      if (manualToggle) {
        manualToggle.addEventListener('click', function() {
          document.getElementById('film-search-wrap').style.display = 'none';
          document.getElementById('film-manual-wrap').style.display = '';
        });
      }
      if (searchToggle) {
        searchToggle.addEventListener('click', function() {
          document.getElementById('film-manual-wrap').style.display = 'none';
          document.getElementById('film-search-wrap').style.display = '';
          var submitBtn = document.getElementById('film-manual-submit');
          if (submitBtn) submitBtn.textContent = 'Link this work';
        });
      }

      /* ---- manual submit ---- */
      var manualSubmit = document.getElementById('film-manual-submit');
      if (manualSubmit) {
        manualSubmit.addEventListener('click', function() {
          var formData = new FormData();
          formData.append('csrfmiddlewaretoken', getCsrf());
          formData.append('media_type', document.getElementById('film-manual-type').value);
          formData.append('title', document.getElementById('film-manual-title').value.trim());
          formData.append('year', document.getElementById('film-manual-year').value);
          formData.append('director', document.getElementById('film-manual-director').value.trim());
          formData.append('runtime_minutes', document.getElementById('film-manual-runtime').value);
          formData.append('certificate', document.getElementById('film-manual-cert').value.trim());
          formData.append('countries', document.getElementById('film-manual-countries').value.trim());
          formData.append('languages', document.getElementById('film-manual-languages').value.trim());
          var errEl = document.getElementById('film-manual-error');
          fetch(manualSubmit.dataset.url, {method: 'POST', body: formData, headers: {'X-Requested-With': 'XMLHttpRequest'}})
          .then(function(r) { return r.json(); })
          .then(function(data) {
            if (data.success) {
              showLinked(data.film);
              suggestFilmInfo(data.suggested_film_information);
              errEl.style.display = 'none';
            } else {
              errEl.textContent = data.error || 'Something went wrong.';
              errEl.style.display = '';
            }
          });
        });
      }

    }); // end DOMContentLoaded
  })();
}
