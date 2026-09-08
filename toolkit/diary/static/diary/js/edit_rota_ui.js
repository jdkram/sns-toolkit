// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-input"
// Extracted from edit_rota.html's second inline <script> block (the UI/filtering/
// keyboard-navigation code -- not the rota-editing AJAX logic, which was already in
// diary/js/edit_rota.js before this pass) (QUALITY_PASS.md Chunk 9).
//
// Several {% if can_mark_events %} / {% if current_volunteer_pk %} blocks guarded
// entire declarations (ROTA_MARKS, setShowingMark, etc.). Rather than wrap those in a
// runtime `if` around `function` declarations -- risky under "use strict", where
// function declarations inside a block are block-scoped and would not be reachable from
// the later `typeof setShowingMark === "function"` checks in the keyboard handler --
// they were converted to `var` bindings assigned via function *expressions* inside the
// `if`, which still hoist to this factory's outer scope. That preserves the exact
// original semantics: when opts.canMarkEvents is false, these stay `undefined`, exactly
// as they were simply never declared before.
function editRotaUI(opts) {
(function($) {
    "use strict";

    // ── Filter panel collapse ──────────────────────────────────────────────
    function setupFilterToggle() {
        $("#rota-filter-toggle").on("click", function() {
            var body       = $("#rota-filter-body");
            var btn        = $(this);
            var isExpanded = btn.attr("aria-expanded") === "true";
            if (isExpanded) {
                body.slideUp(150);
                btn.attr("aria-expanded", "false");
                btn.find(".rota-filter-chevron").text("▸");
            } else {
                body.slideDown(150);
                btn.attr("aria-expanded", "true");
                btn.find(".rota-filter-chevron").text("▾");
            }
        });
    }

    // ── Excluded-count badge ───────────────────────────────────────────────
    function updateFilterStatus() {
        var total    = $(".rota-showing").length;
        var visible  = $(".rota-showing:visible").length;
        var excluded = total - visible;
        var badge    = $("#rota-filter-status");
        if (excluded > 0) {
            badge.text(excluded + " hidden").show();
        } else {
            badge.hide();
        }
    }

    // ── Role badges ────────────────────────────────────────────────────────
    // Badges are driven by data attributes emitted from Role model fields.
    // To add a new badge type: add a field to the Role model + migration,
    // emit a data-* attribute on the <li> in this template, and add an
    // entry to ROLE_BADGES below.
    var ROLE_BADGES = [
        {
            attr: "beginner",
            html: '<span class="role-badge role-badge--beginner" title="Good first role: great for new volunteers">🌱</span>'
        },
        {
            attr: "wheelchair",
            html: '<span class="role-badge role-badge--accessible" title="Confirmed wheelchair-accessible">♿</span>'
        },
        {
            attr: "keyholder",
            html: '<span class="role-badge role-badge--keyholder" title="Keyholder slot: must be filled by a trained venue keyholder">🔑</span>'
        }
    ];

    function injectRoleBadges() {
        $(".rota-showing li[data-role-name]").each(function() {
            var li = $(this);
            $.each(ROLE_BADGES, function(i, badge) {
                if (li.data(badge.attr) === 1) {
                    // Append inside .rota_role so the icon stays with the
                    // role label and never pushes the volunteer name column.
                    // A non-breaking space (rather than a plain one) keeps
                    // the badge glued to the role name's last word instead
                    // of wrapping onto an orphan line of its own.
                    li.find(".rota_role").append(" " + badge.html);
                }
            });
        });
    }

    // ── Role warning badges (needs keyholder / programmer) ────────────────
    // Injects a badge into .showing-meta-tail for future showings that have
    // an unfilled keyholder or programmer slot. Toggled via the controls bar;
    // re-runs on rota:entry-changed so badges clear as slots are filled.
    function applyCriticalSlotWarnings() {
        $(".rota-role-warning-badge").remove();
        if (!$("#rota-show-role-warnings").is(":checked")) { return; }

        $(".rota-showing[data-in-past='0']").each(function() {
            var showing         = $(this);
            var needsKeyholder  = showing.find("li[data-keyholder='1'] .rota_name .na").length > 0;
            var needsProgrammer = showing.find("li[data-programmer='1'] .rota_name .na").length > 0;

            if (!needsKeyholder && !needsProgrammer) { return; }

            var text = needsKeyholder && needsProgrammer
                ? 'needs keyholder + programmer'
                : needsKeyholder ? 'needs keyholder' : 'needs programmer';

            showing.find(".showing-meta-tail").prepend(
                '<span class="rota-role-warning-badge">' + text + '</span>'
            );
        });
    }

    // ── Utilities ─────────────────────────────────────────────────────────
    function debounce(fn, delay) {
        var timer;
        return function() {
            clearTimeout(timer);
            timer = setTimeout(fn, delay);
        };
    }

    // Strips diacritical marks so "cafe" matches "Café", "resume" matches "résumé", etc.
    function foldAccents(str) {
        return str.normalize("NFD").replace(/[\u0300-\u036f]/g, "");
    }

    // ── Tag filter bar: build from data-tags/data-tag-names on each showing ──
    // Reads data attributes (always in the DOM) rather than rendered badge
    // elements, but only when rota_show_tags is on -- see ROTA_SHOW_TAGS above.
    function buildTagFilterBar() {
        if (!ROTA_SHOW_TAGS) { return; }
        var seen = {};
        var tags = [];
        $(".rota-showing[data-tags]").each(function() {
            var slugs = ($(this).attr("data-tags") || "").split(",");
            var names = ($(this).attr("data-tag-names") || "").split("|");
            $.each(slugs, function(i, slug) {
                slug = $.trim(slug);
                if (slug && !seen[slug]) {
                    seen[slug] = true;
                    tags.push({ slug: slug, name: names[i] || slug });
                }
            });
        });

        if (tags.length === 0) { return; }

        var bar = $("#rota-tag-filter-buttons");
        $.each(tags, function(i, tag) {
            bar.append(
                $('<button type="button" class="btn btn-sm btn-outline-secondary rota-tag-btn">')
                    .data("tag-slug", tag.slug)
                    .text(tag.name)
            );
        });

        $(".rota-tag-filters").show();

        bar.on("click", ".rota-tag-btn", function() {
            var btn  = $(this);
            var wasActive = btn.hasClass("active");
            // Single-select: click again to clear.
            $(".rota-tag-btn").removeClass("active btn-secondary").addClass("btn-outline-secondary");
            if (!wasActive) {
                btn.removeClass("btn-outline-secondary").addClass("btn-secondary active");
            }
            applyFilters();
        });
    }

    // ── Build role dropdown from actual rota entries in the DOM ────────────
    function buildRoleDropdown() {
        var seen  = {};
        var roles = [];
        $(".rota-showing li[data-role-name]").each(function() {
            var role = $(this).data("role-name");
            if (role && !seen[role]) {
                seen[role] = true;
                roles.push(role);
            }
        });
        roles.sort();
        var select = $("#rota-filter-role");
        $.each(roles, function(i, role) {
            select.append($("<option>").val(role).text(role));
        });
    }

    // ── Hide month headers that have no visible showings beneath them ───────
    function updateMonthHeaders() {
        $("h2.rota-month-header").each(function() {
            var showingsInMonth = $(this).nextUntil("h2.rota-month-header", ".rota-showing");
            $(this).toggle(showingsInMonth.filter(":visible").length > 0);
        });
        $(".rota-day-group-header").each(function() {
            var showingsInDay = $(this).nextUntil(".rota-day-group-header, h2.rota-month-header", ".rota-showing");
            $(this).toggle(showingsInDay.filter(":visible").length > 0);
        });
    }

    // ── Highlight empty slots ──────────────────────────────────────────────
    // Uses the presence of a .na child on .rota_name — that's the live
    // jeditable placeholder, so it stays accurate after in-page edits.
    function applyEmptyHighlight(enabled) {
        $(".rota-empty-slot").removeClass("rota-empty-slot");
        if (!enabled) { return; }
        $(".rota-showing[data-in-past='0'] li").each(function() {
            if ($(this).find(".rota_name .na").length > 0) {
                $(this).addClass("rota-empty-slot");
            }
        });
    }

    // ── Apply all current filter settings ─────────────────────────────────
    function applyFilters() {
        var selectedRole    = $("#rota-filter-role").val();
        var highlightEmpty  = $("#rota-filter-empty").is(":checked");
        var highlightBeginner = $("#rota-filter-beginner").is(":checked");
        var activeTagBtn    = $(".rota-tag-btn.active");
        var activeTagSlug   = activeTagBtn.length ? activeTagBtn.data("tag-slug") : null;
        var searchTerm      = $.trim($("#rota-search").val()).toLowerCase();
        var onlyStarred = opts.canMarkEvents ? $("#rota-filter-starred").is(":checked") : false;
        var onlyMine    = opts.currentVolunteerPk ? $("#rota-filter-mine").is(":checked") : false;
        var myVolPk     = opts.currentVolunteerPk || "";

        $(".rota-showing").each(function() {
            var showing = $(this);

            if (selectedRole) {
                var hasRole = false;
                showing.find("li[data-role-name]").each(function() {
                    if ($(this).data("role-name") === selectedRole) {
                        hasRole = true;
                        return false;
                    }
                });
                if (!hasRole) { showing.hide(); return; }
            }

            if (activeTagSlug) {
                var showingTags = (showing.data("tags") || "").toString().split(",");
                if ($.inArray(activeTagSlug, showingTags) === -1) {
                    showing.hide(); return;
                }
            }

            if (onlyStarred && showing.attr("data-mark") !== "star") {
                showing.hide(); return;
            }

            if (onlyMine) {
                var signedUp = false;
                showing.find(".rota_name[data-volunteer-id]").each(function() {
                    if ($(this).attr("data-volunteer-id") === myVolPk) {
                        signedUp = true; return false;
                    }
                });
                if (!signedUp) { showing.hide(); return; }
            }

            if (searchTerm) {
                var name = foldAccents(showing.find(".showing-event-name").text().toLowerCase());
                if (name.indexOf(foldAccents(searchTerm)) === -1) { showing.hide(); return; }
            }

            showing.show();
        });

        updateMonthHeaders();
        applyEmptyHighlight(highlightEmpty);
        $(".rota-wrapper").toggleClass("rota-beginner-active", highlightBeginner);
        updateFilterStatus();
    }

    // ── Event mark toggle (☆ → ★ → ☽ → ☆) ───────────────────────────────
    // ROTA_MARKS/setShowingMark etc. are always declared (var-hoisted to this
    // outer scope) so later code can safely `typeof setShowingMark ===
    // "function"` check them, but only ever populated/wired up when
    // opts.canMarkEvents -- when it's false, rota_marks_json is always "{}"
    // server-side and no .rota-mark-toggle elements exist in the DOM, so
    // this being present-but-inert is harmless either way.
    var ROTA_MARKS, MARK_TOGGLE_URL, MARK_CYCLE, MARK_ICON, MARK_TITLE;
    var setToggleState, setShowingMark, initMarkButtons;
    if (opts.canMarkEvents) {
    ROTA_MARKS      = opts.rotaMarksJson;
    MARK_TOGGLE_URL = opts.toggleEventMarkUrl;
    MARK_CYCLE = { "": "star", "star": "shadow", "shadow": "" };
    MARK_ICON  = { "": "☆", "star": "★", "shadow": "☽" };
    MARK_TITLE = {
        "":       "Click to bookmark this event",
        "star":   "★ Bookmarked, click for ☽ deprioritise",
        "shadow": "☽ Deprioritised, click to clear"
    };

    setToggleState = function(btn, markType) {
        var showing = btn.closest(".rota-showing");
        btn.data("mark", markType).attr("data-mark", markType);
        btn.text(MARK_ICON[markType]);
        btn.attr("title", MARK_TITLE[markType]);
        showing.attr("data-mark", markType);
        showing.toggleClass("rota-mooned", markType === "shadow");
        applyShowingHighlights();
    };

    // Direct mark jump for keyboard shortcuts (bypasses the cycle).
    setShowingMark = function(showing, targetMark) {
        var btn = showing.find(".rota-mark-toggle");
        if (!btn.length || btn.prop("disabled")) { return; }
        if ((btn.attr("data-mark") || "") === targetMark) { return; }
        var eventId = btn.data("event-id");
        btn.prop("disabled", true);
        $.ajax({
            url:  MARK_TOGGLE_URL,
            type: "POST",
            data: { mark_type: targetMark, event_id: eventId, csrfmiddlewaretoken: opts.csrfToken },
            success: function(resp) { setToggleState(btn, resp.mark_type); },
            complete: function() { btn.prop("disabled", false); }
        });
    };

    initMarkButtons = function() {
        $(".rota-mark-toggle").each(function() {
            var btn     = $(this);
            var eventId = parseInt(btn.data("event-id"), 10);
            setToggleState(btn, ROTA_MARKS[eventId] || "");
        });
    };

    $(document).on("click", ".rota-mark-toggle", function() {
        var btn     = $(this);
        var eventId = btn.data("event-id");
        var current = btn.attr("data-mark") || "";
        var next    = MARK_CYCLE[current];
        btn.prop("disabled", true);
        $.ajax({
            url:  MARK_TOGGLE_URL,
            type: "POST",
            data: { mark_type: next, event_id: eventId, csrfmiddlewaretoken: opts.csrfToken },
            success: function(resp) { setToggleState(btn, resp.mark_type); },
            complete: function() { btn.prop("disabled", false); }
        });
    });
    }

    // ── Month navigation rail ──────────────────────────────────────────────
    var ROTA_NEXT_BATCH_URL = (function() {
        var p = opts.endDateYmd.split("-");
        return opts.rotaEditUrl + "/" +
            p[0] + "/" + parseInt(p[1], 10) + "/" + parseInt(p[2], 10) +
            "?daysahead=" + opts.daysAhead;
    })();

    function buildNavRail() {
        var headers = $("h2.rota-month-header");
        if (headers.length < 1) {
            $("#rota-nav-rail").hide();
            return;
        }

        var inner  = $("#rota-nav-rail .rail-inner");
        var cursor = $(".rail-cursor");

        // Build sorted list of all showing dates so we can find nearest-previous
        // for any given Monday that has no showing of its own.
        var showingDates   = [];
        var showingDateMap = {}; // "YYYY-MM-DD" → day-group header element
        $(".rota-day-group-header[data-date]").each(function() {
            var ds = $(this).attr("data-date");
            showingDates.push(ds);
            showingDateMap[ds] = this;
        });
        showingDates.sort();

        function nearestShowingOnOrBefore(targetDateStr) {
            var lo = 0, hi = showingDates.length - 1, result = null;
            while (lo <= hi) {
                var mid = (lo + hi) >> 1;
                if (showingDates[mid] <= targetDateStr) { result = showingDates[mid]; lo = mid + 1; }
                else                                    { hi = mid - 1; }
            }
            return result ? showingDateMap[result] : null;
        }

        // All Mondays (day-of-month numbers) in a given year+month (1-indexed).
        function mondaysInMonth(year, month) {
            var mondays = [];
            var d = new Date(year, month - 1, 1);
            var daysToFirst = d.getDay() === 1 ? 0 : (8 - d.getDay()) % 7;
            var daysInMonth = new Date(year, month, 0).getDate();
            for (var day = 1 + daysToFirst; day <= daysInMonth; day += 7) {
                mondays.push(day);
            }
            return mondays;
        }

        headers.each(function(i) {
            var h      = $(this);
            var parts  = h.text().trim().split(" ");   // ["April", "2026"]
            var label  = parts[0].slice(0, 3) + " '" + (parts[1] || "").slice(2); // "Apr '26"
            var year   = parseInt(h.attr("data-year"),  10);
            var month  = parseInt(h.attr("data-month"), 10);

            $('<span class="rail-month rail-month-label">').text(label)
                .on("click", function() {
                    h[0].scrollIntoView({ behavior: "smooth", block: "start" });
                })
                .appendTo(inner);

            // Show all Mondays in this month; each links to the nearest showing
            // on or before that Monday (so the user lands at the closest relevant entry).
            var mondays = mondaysInMonth(year, month);
            $.each(mondays, function(_, day) {
                var pad = ("0" + month).slice(-2);
                var dayPad = ("0" + day).slice(-2);
                var dateStr = year + "-" + pad + "-" + dayPad;
                var targetEl = nearestShowingOnOrBefore(dateStr);
                if (!targetEl) { return; } // no showings yet loaded before this date
                $('<span class="rail-monday">').text(day)
                    .attr("title", "Mon " + day + " " + parts[0])
                    .on("click", (function(el) {
                        return function() { el.scrollIntoView({ behavior: "smooth", block: "start" }); };
                    })(targetEl))
                    .appendTo(inner);
            });
        });

        $('<span class="rail-month rail-later">').text("Later ↓")
            .on("click", function() {
                var anchor = document.getElementById("rota-later-anchor");
                if (anchor) { anchor.scrollIntoView({ behavior: "smooth" }); }
            })
            .appendTo(inner);

        $('<a class="rail-month rail-next-batch">').text("Next →")
            .attr("href", ROTA_NEXT_BATCH_URL)
            .appendTo(inner);

        cursor.appendTo(inner); // keep cursor as last child in DOM

        function updateRail() {
            var scrollY    = window.scrollY;
            var docH       = document.body.scrollHeight;
            var winH       = window.innerHeight;
            var scrollFrac = docH > winH ? scrollY / (docH - winH) : 0;
            var railH      = inner.height();

            cursor.css("top", Math.round(scrollFrac * railH) + "px");

            var navH    = document.querySelector(".navbar.fixed-top").offsetHeight;
            var current = null;
            headers.each(function() {
                if (this.getBoundingClientRect().top <= navH + 20) { current = this; }
            });
            inner.find(".rail-month-label").removeClass("rail-active");
            if (current) {
                inner.find(".rail-month-label").eq(headers.index(current)).addClass("rail-active");
            }
        }

        window.addEventListener("scroll", updateRail, { passive: true });
        updateRail();
    }

    // ── Role badge visibility preferences ─────────────────────────────────
    // Three toggles persisted in localStorage.
    // defaultVisible: beginner = true (shown by default); wheelchair/keyholder = false (opt-in).
    var BADGE_PREFS = [
        { key: "rota_badge_beginner",    cls: "rota-hide-beginner",    id: "badge-pref-beginner",    defaultVisible: true  },
        { key: "rota_badge_wheelchair",  cls: "rota-hide-wheelchair",  id: "badge-pref-wheelchair",  defaultVisible: false },
        { key: "rota_badge_keyholder",   cls: "rota-hide-keyholder",   id: "badge-pref-keyholder",   defaultVisible: false }
    ];

    // Server hint: returning (Dormant) volunteers get the beginner highlight
    // forced on for this page load, overriding any stored "off" preference, to
    // help them ease back in. They can still toggle it off again.
    var FORCE_BEGINNER = opts.forceBeginnerHighlight;

    var ROTA_SHOW_TAGS = opts.rotaShowTags;

    function initBadgeToggles() {
        var wrapper = $(".rota-wrapper");
        $.each(BADGE_PREFS, function(i, pref) {
            var stored = localStorage.getItem(pref.key);
            var show = stored !== null ? (stored === "1") : pref.defaultVisible;
            if (pref.key === "rota_badge_beginner" && FORCE_BEGINNER) { show = true; }
            if (!show) { wrapper.addClass(pref.cls); }
            var cb = document.getElementById(pref.id);
            if (cb) {
                cb.checked = show;
                $(cb).on("change", function() {
                    var visible = this.checked;
                    wrapper.toggleClass(pref.cls, !visible);
                    localStorage.setItem(pref.key, visible ? "1" : "0");
                });
            }
        });

        // Role warnings toggle — dynamically computed so handled separately.
        var warningsCb = document.getElementById("rota-show-role-warnings");
        if (warningsCb) {
            var storedWarnings = localStorage.getItem("rota_role_warnings");
            var showWarnings = storedWarnings !== null ? (storedWarnings === "1") : true;
            warningsCb.checked = showWarnings;
            $(warningsCb).on("change", function() {
                localStorage.setItem("rota_role_warnings", this.checked ? "1" : "0");
                applyCriticalSlotWarnings();
            });
        }
    }

    // ── Per-showing highlights: my shifts (green) and starred (amber) ────
    // "Mine" takes precedence — if both apply, only --mine is set.
    function applyShowingHighlights() {
        var myVolPk = opts.currentVolunteerPk || "";
        $(".rota-showing").each(function() {
            var showing = $(this);
            showing.removeClass("rota-showing--mine rota-showing--starred");
            if (opts.currentVolunteerPk) {
            var isMine = false;
            showing.find(".rota_name[data-volunteer-id]").each(function() {
                var nameSpan = $(this);
                var mine = nameSpan.attr("data-volunteer-id") === myVolPk && myVolPk !== "";
                nameSpan.toggleClass("rota_name--mine", mine);
                if (mine) {
                    isMine = true;
                    if (!nameSpan.next(".rota-name-you-tag").length) {
                        nameSpan.after('<span class="rota-name-you-tag">(you)</span>');
                    }
                } else {
                    nameSpan.next(".rota-name-you-tag").remove();
                }
            });
            if (isMine) { showing.addClass("rota-showing--mine"); return; }
            }
            if (opts.canMarkEvents) {
            if (showing.attr("data-mark") === "star") {
                showing.addClass("rota-showing--starred");
            }
            }
        });
    }

    function updateDayHeaderOffset() {
        var navbarHeight = document.querySelector('.navbar.fixed-top').offsetHeight;
        var firstDayHeader = document.querySelector('.rota-day-group-header');
        var dayHeaderHeight = firstDayHeader ? firstDayHeader.offsetHeight : 40;
        var showingMargin = navbarHeight + dayHeaderHeight;
        document.querySelectorAll('.rota-day-group-header').forEach(function(el) {
            el.style.top = navbarHeight + 'px';
            el.style.scrollMarginTop = navbarHeight + 'px';
        });
        document.querySelectorAll('.rota-showing').forEach(function(el) {
            el.style.scrollMarginTop = showingMargin + 'px';
        });
    }
    window.addEventListener('resize', updateDayHeaderOffset);

    // ── Keyboard navigation and shortcuts ─────────────────────────────────
    function setupKeyboardNavigation() {

        function stickyOffset() {
            var nav  = document.querySelector('.navbar.fixed-top');
            var dayH = document.querySelector('.rota-day-group-header');
            return (nav ? nav.offsetHeight : 58) + (dayH ? dayH.offsetHeight : 36) + 8;
        }

        function getCurrentShowing() {
            var showings = $(".rota-showing:visible").toArray();
            if (!showings.length) { return null; }
            var threshold = stickyOffset();
            var current = showings[0];
            for (var i = 0; i < showings.length; i++) {
                if (showings[i].getBoundingClientRect().top <= threshold) { current = showings[i]; }
            }
            return current;
        }

        function navigateShowings(direction) {
            var showings = $(".rota-showing:visible").toArray();
            if (!showings.length) { return; }
            var idx = showings.indexOf(getCurrentShowing());
            var target = direction > 0
                ? Math.min(idx + 1, showings.length - 1)
                : Math.max(idx - 1, 0);
            showings[target].scrollIntoView({ behavior: "smooth", block: "start" });
        }

        function navigateDays(direction) {
            var headers = $(".rota-day-group-header:visible").toArray();
            if (!headers.length) { return; }
            var threshold = stickyOffset();
            var idx = 0;
            for (var i = 0; i < headers.length; i++) {
                if (headers[i].getBoundingClientRect().top <= threshold + 5) { idx = i; }
            }
            var target = direction > 0
                ? Math.min(idx + 1, headers.length - 1)
                : Math.max(idx - 1, 0);
            headers[target].scrollIntoView({ behavior: "smooth", block: "start" });
        }

        function navigateWeeks(direction) {
            var headers = $(".rota-day-group-header:visible").toArray();
            if (!headers.length) { return; }
            var threshold = stickyOffset();
            var currentIdx = 0;
            for (var i = 0; i < headers.length; i++) {
                if (headers[i].getBoundingClientRect().top <= threshold + 5) { currentIdx = i; }
            }
            var current = new Date($(headers[currentIdx]).data("date"));
            var target = new Date(current);
            target.setDate(target.getDate() + direction * 7);
            var best = currentIdx, bestDiff = Infinity;
            for (var i = 0; i < headers.length; i++) {
                var d = new Date($(headers[i]).data("date"));
                var diff = Math.abs(d - target);
                if (diff < bestDiff) { bestDiff = diff; best = i; }
            }
            headers[best].scrollIntoView({ behavior: "smooth", block: "start" });
        }

        function showToast(msg) {
            $('#rota-toast').remove();
            var toast = $('<div id="rota-toast">').text(msg).appendTo('body');
            setTimeout(function() { toast.addClass('rota-toast-fade'); }, 50);
            setTimeout(function() { toast.remove(); }, 2000);
        }

        // ── Help modal ────────────────────────────────────────────────────
        var helpVisible = false;

        function buildHelpModal() {
            if (document.getElementById('rota-kb-help')) { return; }
            var canMark    = !!$(".rota-mark-toggle").length;
            var canEdit    = !!$("a.showing-event-name[href*='edit']").length;
            var hasStar    = !!document.getElementById('rota-filter-starred');
            var hasMine    = !!document.getElementById('rota-filter-mine');
            var sections = [
                { heading: "Navigate", rows: [
                    ["j / k",        "Next / previous showing"],
                    ["] / [",        "Next / previous day"],
                    ["J / }",        "Forward one week"],
                    ["K / {",        "Back one week"],
                    ["g → g",        "First showing"],
                    ["g → key",      "Go to page (badges appear on nav)"],
                    ["G",            "Last showing"]
                ]},
                { heading: "Current showing", rows: [
                    canEdit ? ["e / h", "Jump to event hub"] : null,
                    ["r",   "Sign up for a role (fuzzy picker)"],
                    ["n",   "Edit rota notes"],
                    ["o / x", "Open public view (new tab)"],
                    ["y / l", "Copy permalink to clipboard"]
                ].filter(Boolean)},
                canMark ? { heading: "Marks", rows: [
                    ["s",         "Cycle mark  ☆ → ★ → ☽ → ☆"],
                    ["1 / 2 / 0", "Star ★ / shadow ☽ / clear ☆"]
                ]} : null,
                (hasStar || hasMine) ? { heading: "Filters", rows: [
                    hasStar ? ["*", "Toggle Starred filter"]    : null,
                    hasMine ? ["f", "Toggle My shifts filter"]  : null
                ].filter(Boolean)} : null,
                { heading: "Search", rows: [
                    ["/",   "Focus search (event names, volunteers)"],
                    ["F",   "Focus search (alternative)"],
                    ["Esc", "Clear search  ·  close overlays"]
                ]},
                { heading: "Help", rows: [
                    ["?", "Toggle this panel"]
                ]}
            ].filter(Boolean);

            var html = '<div id="rota-kb-help" tabindex="-1" role="dialog" aria-modal="true" aria-label="Keyboard shortcuts">' +
                '<div class="rota-kb-help-card">' +
                '<div class="rota-kb-help-header"><strong>Keyboard shortcuts</strong>' +
                '<button class="rota-kb-help-close" aria-label="Close">&#x2715;</button></div>';

            $.each(sections, function(i, section) {
                html += '<div class="rota-kb-section"><div class="rota-kb-section-heading">' +
                    section.heading + '</div>';
                $.each(section.rows, function(j, row) {
                    html += '<div class="rota-kb-row"><kbd>' + row[0] + '</kbd><span>' + row[1] + '</span></div>';
                });
                html += '</div>';
            });
            html += '</div></div>';

            $('body').append(html);
            $('#rota-kb-help').on('click', function(e) {
                if ($(e.target).is('#rota-kb-help') || $(e.target).hasClass('rota-kb-help-close')) {
                    toggleHelp(false);
                }
            });
        }

        function toggleHelp(force) {
            buildHelpModal();
            helpVisible = force !== undefined ? force : !helpVisible;
            $('#rota-kb-help').toggle(helpVisible);
            if (helpVisible) { $('#rota-kb-help').focus(); }
        }

        // ── Role signup picker ─────────────────────────────────────────────
        function escHtml(str) { return $('<span>').text(str || "").html(); }

        function openSignupModal(showing) {
            $('#rota-signup-modal').remove();

            var myPk  = (opts.currentVolunteerPk || "").toString();
            var roles = [];
            showing.find(".rota > li").each(function() {
                var li       = $(this);
                var nameSpan = li.find(".rota_name");
                if (!nameSpan.length) { return; }
                var entryId  = nameSpan.attr("id");
                var volId    = (nameSpan.attr("data-volunteer-id") || "").toString();
                var isMine   = !!(myPk && volId === myPk);
                var isAvail  = nameSpan.hasClass("rota-signup-available");
                var takenName = (!isAvail && !isMine && volId) ? $.trim(nameSpan.text()) : "";
                roles.push({ entryId: entryId, roleName: li.attr("data-role-name") || "Role",
                              isMine: isMine, isAvail: isAvail, takenName: takenName });
            });

            if (!roles.length) { return; }

            roles.sort(function(a, b) {
                if (a.isMine  !== b.isMine)  { return a.isMine  ? -1 : 1; }
                if (a.isAvail !== b.isAvail) { return a.isAvail ? -1 : 1; }
                return a.roleName.localeCompare(b.roleName);
            });

            var listItems = "";
            $.each(roles, function(i, role) {
                var cls = "rota-signup-role-item";
                var text;
                if (role.isMine) {
                    cls  += " rota-signup-role-mine";
                    text  = "✓ " + role.roleName + ", signed up (Enter to unsign)";
                } else if (role.isAvail) {
                    cls  += " rota-signup-role-available";
                    text  = role.roleName;
                } else {
                    cls  += " rota-signup-role-taken";
                    text  = role.roleName + (role.takenName ? ": " + role.takenName : ": taken");
                }
                listItems += '<li class="' + cls + '" data-entry-id="' + escHtml(role.entryId) +
                    '" data-role-name="' + escHtml(role.roleName) + '">' + escHtml(text) + '</li>';
            });

            $('body').append(
                '<div id="rota-signup-modal" tabindex="-1" role="dialog" aria-modal="true" aria-label="Sign up for a role">' +
                '<div class="rota-signup-card">' +
                '<div class="rota-signup-header"><strong>Sign up for a role</strong>' +
                '<button class="rota-signup-close" aria-label="Close">&#x2715;</button></div>' +
                '<input type="text" id="rota-signup-search" class="form-control form-control-sm" placeholder="Filter roles…" autocomplete="off">' +
                '<ul id="rota-signup-role-list">' + listItems + '</ul>' +
                '</div></div>'
            );

            var searchInput = $('#rota-signup-search');
            var roleList    = $('#rota-signup-role-list');

            setTimeout(function() { searchInput.focus(); }, 10);

            $('#rota-signup-modal').on('click', function(e) {
                if ($(e.target).is('#rota-signup-modal') || $(e.target).hasClass('rota-signup-close')) {
                    closeSignupModal();
                }
            });

            searchInput.on('input', function() {
                var term = $(this).val().toLowerCase();
                roleList.children("li").each(function() {
                    $(this).toggle(($(this).data("role-name") || "").toString().toLowerCase().indexOf(term) !== -1);
                });
                roleList.children("li.rota-signup-role-active").removeClass("rota-signup-role-active");
                roleList.children("li:visible:first").addClass("rota-signup-role-active");
            });

            searchInput.on('keydown', function(e) {
                if (e.key === "Escape") { e.stopPropagation(); closeSignupModal(); return; }
                if (e.key === "ArrowDown" || e.key === "ArrowUp") {
                    e.preventDefault();
                    var items   = roleList.children("li:visible");
                    var active  = roleList.children("li.rota-signup-role-active");
                    var idx     = items.index(active);
                    var nextIdx = e.key === "ArrowDown"
                        ? Math.min(idx + 1, items.length - 1)
                        : Math.max(idx - 1, 0);
                    active.removeClass("rota-signup-role-active");
                    $(items[nextIdx]).addClass("rota-signup-role-active");
                }
                if (e.key === "Enter") {
                    e.preventDefault();
                    var target = roleList.children("li.rota-signup-role-active:visible");
                    if (!target.length) {
                        target = roleList.children("li.rota-signup-role-available:visible, li.rota-signup-role-mine:visible").first();
                    }
                    if (target.length) { target.trigger("click"); }
                }
            });

            roleList.on('click', 'li.rota-signup-role-available, li.rota-signup-role-mine', function() {
                var entryId = $(this).data('entry-id');
                if (!entryId) { return; }
                closeSignupModal();
                $('#' + entryId).trigger('click');
            });

            var mineItem  = roleList.children("li.rota-signup-role-mine:first");
            var firstAvail = roleList.children("li.rota-signup-role-available:first");
            (mineItem.length ? mineItem : firstAvail).addClass("rota-signup-role-active");
        }

        function closeSignupModal() { $('#rota-signup-modal').remove(); }

        // Ctrl+Enter in notes textarea submits the jeditable form
        $(document).on('keydown', '.showing_rota_notes textarea, .past_showing_rota_notes textarea', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                e.preventDefault();
                $(this).closest('form').find('.rota-notes-save').trigger('click');
            }
        });

        // ── Key handler ───────────────────────────────────────────────────
        var lastKey = null, lastKeyTime = 0;

        $(document).on("keydown", function(e) {
            // Yield to global nav handler while it owns g-key nav mode
            if (window.AdminKeyboardNav && window.AdminKeyboardNav.isNavMode()) { return; }

            if (e.ctrlKey || e.altKey || e.metaKey) { return; }
            var tag     = (document.activeElement || {}).tagName || "";
            var inInput = /^(INPUT|TEXTAREA|SELECT)$/i.test(tag);
            var inEdit  = !!(document.activeElement && document.activeElement.isContentEditable);

            // Escape: always handle regardless of focus
            if (e.key === "Escape") {
                if ($('#rota-signup-modal').length) { closeSignupModal(); return; }
                if (helpVisible) { toggleHelp(false); return; }
                var search = document.getElementById('rota-search');
                if (search && search.value) {
                    $(search).val("").trigger("input");
                    search.blur();
                }
                return;
            }

            if (inInput || inEdit) { return; }

            var now = Date.now();
            var key = e.key;

            lastKey = key;
            lastKeyTime = now;

            switch (key) {
                // Navigation
                case "j":
                    e.preventDefault(); navigateShowings(1); break;
                case "k":
                    e.preventDefault(); navigateShowings(-1); break;
                case "J": case "}":
                    e.preventDefault(); navigateWeeks(1); break;
                case "K": case "{":
                    e.preventDefault(); navigateWeeks(-1); break;
                case "]":
                    e.preventDefault(); navigateDays(1); break;
                case "[":
                    e.preventDefault(); navigateDays(-1); break;
                case "G":
                    e.preventDefault();
                    var lastShowing = $(".rota-showing:visible").last()[0];
                    if (lastShowing) { lastShowing.scrollIntoView({ behavior: "smooth", block: "start" }); }
                    break;

                // Current showing: event hub / public view / permalink / notes / signup
                case "e": case "h": {
                    var editShowing = getCurrentShowing();
                    if (!editShowing) { break; }
                    var editHref = $(editShowing).find("a.showing-event-name[href]").attr("href");
                    if (editHref) { window.location.href = editHref; }
                    break;
                }
                case "o": case "x": {
                    var openShowing = getCurrentShowing();
                    if (!openShowing) { break; }
                    var openHref = $(openShowing).find(".showing-public-link[href]").attr("href");
                    if (openHref) { window.open(openHref, "_blank", "noopener"); }
                    break;
                }
                case "y": case "l": {
                    var yankShowing = getCurrentShowing();
                    if (yankShowing) {
                        $(yankShowing).find(".showing-anchor-link").trigger("click");
                        showToast("Link copied");
                    }
                    break;
                }
                case "n": {
                    var notesShowing = getCurrentShowing();
                    if (!notesShowing) { break; }
                    e.preventDefault();
                    $(notesShowing).find(".showing_rota_notes span").first().trigger("click");
                    break;
                }
                case "r": {
                    var sigShowing = getCurrentShowing();
                    if (!sigShowing) { break; }
                    e.preventDefault();
                    openSignupModal($(sigShowing));
                    break;
                }

                // Marks (s = cycle; 1/2/0 = direct)
                case "s": {
                    var markShowing = getCurrentShowing();
                    if (markShowing) { $(markShowing).find(".rota-mark-toggle").trigger("click"); }
                    break;
                }
                case "1": {
                    var mark1Showing = getCurrentShowing();
                    if (mark1Showing && typeof setShowingMark === "function") {
                        setShowingMark($(mark1Showing), "star");
                    }
                    break;
                }
                case "2": {
                    var mark2Showing = getCurrentShowing();
                    if (mark2Showing && typeof setShowingMark === "function") {
                        setShowingMark($(mark2Showing), "shadow");
                    }
                    break;
                }
                case "0": {
                    var mark0Showing = getCurrentShowing();
                    if (mark0Showing && typeof setShowingMark === "function") {
                        setShowingMark($(mark0Showing), "");
                    }
                    break;
                }

                // Filter toggles
                case "*": {
                    var scb = document.getElementById('rota-filter-starred');
                    if (scb) { $(scb).prop('checked', !scb.checked).trigger('change'); }
                    break;
                }
                case "f": {
                    var fcb = document.getElementById('rota-filter-mine');
                    if (fcb) { $(fcb).prop('checked', !fcb.checked).trigger('change'); }
                    break;
                }

                // Search
                case "/":
                case "F":
                    e.preventDefault();
                    $("#rota-search").focus().select();
                    break;

                // Help
                case "?":
                    e.preventDefault();
                    toggleHelp();
                    break;
            }
        });
    }

    // ── Role description tap-to-reveal ────────────────────────────────────
    function setupRoleDescriptions() {
        $(document).on("click", ".rota_role--described", function() {
            var role = $(this);
            var li = role.closest("li");
            var existing = role.next(".rota-role-desc");
            if (existing.length) {
                existing.remove();
                li.find(".rota-signup-prompt").text("—");
            } else {
                $('<span class="rota-role-desc">').text(role.attr("title")).insertAfter(role);
                li.find(".rota-signup-prompt").text("Tap to sign up");
            }
        });
    }

    $(document).ready(function() {
        updateDayHeaderOffset();
        setupFilterToggle();
        buildNavRail();
        buildRoleDropdown();
        buildTagFilterBar();
        injectRoleBadges();
        initBadgeToggles();
        applyCriticalSlotWarnings();
        setupRoleDescriptions();
        setupKeyboardNavigation();
        if (window.AdminKeyboardNav) { window.AdminKeyboardNav.suppressGlobalHelp(); }
        if (opts.canMarkEvents) { initMarkButtons(); }
        applyShowingHighlights();

        // Clicking a tag badge on any showing activates that tag in the
        // filter bar at the top, exactly as if the user had clicked the
        // filter button directly.
        $(document).on("click", ".event-tag", function() {
            var slug = $(this).data("tag-slug");
            var btn = null;
            $(".rota-tag-btn").each(function() {
                if ($(this).data("tag-slug") === slug) { btn = $(this); return false; }
            });
            if (btn) {
                btn.trigger("click");
                $(".rota-controls")[0].scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        });

        var filterSelectors = ["#rota-filter-role", "#rota-filter-empty", "#rota-filter-beginner"];
        if (opts.canMarkEvents) { filterSelectors.push("#rota-filter-starred"); }
        if (opts.currentVolunteerPk) { filterSelectors.push("#rota-filter-mine"); }
        $(filterSelectors.join(", "))
            .on("change", applyFilters);

        // Re-apply empty-slot highlights and keyholder warnings after a sign-up or clear.
        $(document).on("rota:entry-changed", function() {
            applyEmptyHighlight($("#rota-filter-empty").is(":checked"));
            applyCriticalSlotWarnings();
            applyFilters();
            applyShowingHighlights();
        });

        $("#rota-search").on("input", debounce(applyFilters, 200));
    });

})(jQuery);

document.addEventListener('DOMContentLoaded', function () {
    var hash = window.location.hash;
    if (!hash || hash.indexOf('#showing-') !== 0) return;
    var target = document.querySelector(hash);
    if (!target) return;
    target.classList.add('rota-showing--linked');
    target.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
});
}
