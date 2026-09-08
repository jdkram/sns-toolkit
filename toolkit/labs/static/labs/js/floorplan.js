// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Sonnet 5"]; status: "#ai-input"
// Extracted verbatim from labs/floorplan.html's inline <script> (QUALITY_PASS.md Chunk 9).
// Wrapped as a factory function per the edit_rota.js precedent: the template still renders
// the data (notes/items/photos JSON, CSRF token, URL templates) but hands them in as
// arguments rather than interpolating them into the script body itself.
function floorplan(
  notes,
  loftItems,
  areaPhotos,
  CSRF,
  noteUrlTmpl,
  itemCreateTmpl,
  itemTmpl,
  itemPhotoTmpl,
  photoDeleteTmpl,
  areaPhotoTmpl,
  areaPhotoDeleteTmpl,
  svgUrl
) {
  "use strict";

  var NOTE_URL_BASE = noteUrlTmpl.replace("/ROOM_ID/", "/");
  var ITEM_CREATE_BASE = itemCreateTmpl.replace("/ZONE_ID/", "/");
  var ITEM_BASE = itemTmpl.replace("/0/", "/");
  var ITEM_PHOTO_BASE = itemPhotoTmpl.replace("/0/", "/");
  var PHOTO_DELETE_BASE = photoDeleteTmpl.replace("/0/", "/");
  var AREA_PHOTO_TMPL = areaPhotoTmpl;
  var AREA_PHOTO_DELETE_TMPL = areaPhotoDeleteTmpl;

  var svgEl = null;
  var selectedMapId = null;
  var activeTab = "groundfloor";
  var pendingPhotoUpload = null;
  var pendingAreaPhotoId = null;

  function noteUrl(id) { return NOTE_URL_BASE + id + "/"; }
  function itemCreateUrl(zoneId) { return ITEM_CREATE_BASE + zoneId + "/items/"; }
  function itemUrl(id) { return ITEM_BASE + id + "/"; }
  function itemPhotoUrl(id) { return ITEM_PHOTO_BASE + id + "/photo/"; }
  function photoDeleteUrl(id) { return PHOTO_DELETE_BASE + id + "/delete/"; }
  function areaPhotoUrl(areaId) { return AREA_PHOTO_TMPL.replace("AREA_ID", areaId); }
  function areaPhotoDeleteUrl(areaId) { return AREA_PHOTO_DELETE_TMPL.replace("AREA_ID", areaId); }

  function fmtDate(iso) {
    if (!iso) return "";
    return new Date(iso).toLocaleString("en-GB", {dateStyle: "medium", timeStyle: "short"});
  }
  function fmtMeta(note) {
    if (!note || !note.updated_at) return "";
    return "Updated " + fmtDate(note.updated_at) + (note.updated_by ? " by " + note.updated_by : "");
  }

  /* ══════════════════════════════════════════════════════════
     TAB SWITCHING
  ══════════════════════════════════════════════════════════ */
  function switchTab(tab) {
    activeTab = tab;
    document.getElementById("groundfloor-panel").style.display = tab === "groundfloor" ? "" : "none";
    document.getElementById("loft-panel").style.display = tab === "loft" ? "" : "none";
    document.getElementById("tab-groundfloor-btn").classList.toggle("active", tab === "groundfloor");
    document.getElementById("tab-loft-btn").classList.toggle("active", tab === "loft");
    document.getElementById("tab-groundfloor-btn").setAttribute("aria-selected", tab === "groundfloor");
    document.getElementById("tab-loft-btn").setAttribute("aria-selected", tab === "loft");
    document.getElementById("map-hint").textContent = tab === "groundfloor"
      ? "Click a room on the map to jump to its note card. Underlined labels have notes."
      : "Click a zone on the map to jump to its card.";

    if (svgEl) {
      var layer3 = svgEl.getElementById("layer3");
      var layer4 = svgEl.getElementById("layer4");
      var layer5 = svgEl.getElementById("layer5");
      if (layer3) layer3.style.display = tab === "groundfloor" ? "inline" : "none";
      if (layer4) layer4.style.display = tab === "groundfloor" ? "inline" : "none";
      if (layer5) layer5.style.display = tab === "loft" ? "inline" : "none";
    }

    if (selectedMapId) {
      var prev = svgEl && svgEl.getElementById(selectedMapId);
      if (prev) prev.classList.remove("map-selected");
      selectedMapId = null;
    }
  }

  document.getElementById("tab-groundfloor-btn").addEventListener("click", function () { switchTab("groundfloor"); });
  document.getElementById("tab-loft-btn").addEventListener("click", function () { switchTab("loft"); });

  /* ══════════════════════════════════════════════════════════
     GROUND FLOOR: card population + editing (unchanged logic)
  ══════════════════════════════════════════════════════════ */
  function populateRoomCard(card) {
    var roomId = card.dataset.roomId;
    var note = notes[roomId];
    var noteText = card.querySelector(".room-note-text");
    var meta = card.querySelector(".room-note-meta");
    if (note && note.body) {
      noteText.textContent = note.body;
      noteText.classList.remove("empty");
      meta.textContent = fmtMeta(note);
    } else {
      noteText.textContent = "No note yet";
      noteText.classList.add("empty");
      meta.textContent = "";
    }
  }

  function populateAllRooms() {
    document.querySelectorAll(".room-card").forEach(populateRoomCard);
    updateSectionCounts();
    updateRoomSummary();
  }

  function updateSectionCounts() {
    document.querySelectorAll(".section-note-count").forEach(function (badge) {
      var section = badge.dataset.section;
      var cards = document.querySelectorAll('.room-card[data-section="' + section + '"]');
      var count = 0;
      cards.forEach(function (c) {
        if (notes[c.dataset.roomId] && notes[c.dataset.roomId].body) count++;
      });
      badge.textContent = count + "/" + cards.length;
      badge.style.display = count > 0 ? "" : "none";
    });
  }

  function updateRoomSummary() {
    var total = document.querySelectorAll(".room-card").length;
    var noted = Object.keys(notes).filter(function (k) {
      return notes[k].body && k.indexOf("loft-") !== 0;
    }).length;
    var el = document.getElementById("rooms-summary");
    el.textContent = noted === 0
      ? "No rooms have notes yet. Click Edit on any card to add one."
      : noted + " of " + total + " rooms have notes.";
  }

  var activeRoomCardId = null;

  function openRoomCard(card) {
    if (activeRoomCardId && activeRoomCardId !== card.dataset.roomId) {
      var prev = document.querySelector('.room-card[data-room-id="' + activeRoomCardId + '"]');
      if (prev) closeRoomCard(prev);
    }
    var roomId = card.dataset.roomId;
    activeRoomCardId = roomId;
    var note = notes[roomId] || {};
    card.querySelector(".room-note-input").value = note.body || "";
    card.querySelector(".room-note-meta-edit").textContent = fmtMeta(note);
    card.querySelector(".room-save-status").style.display = "none";
    card.classList.add("editing");
    card.querySelector(".room-note-input").focus();
  }

  function closeRoomCard(card) {
    card.classList.remove("editing");
    if (activeRoomCardId === card.dataset.roomId) activeRoomCardId = null;
  }

  function saveRoomCard(card, body) {
    var roomId = card.dataset.roomId;
    var status = card.querySelector(".room-save-status");
    status.style.display = "none";
    fetch(noteUrl(roomId), {
      method: "POST",
      headers: {"Content-Type": "application/json", "X-CSRFToken": CSRF},
      body: JSON.stringify({body: body})
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) throw new Error(data.error);
      notes[roomId] = data;
      populateRoomCard(card);
      card.querySelector(".room-note-meta-edit").textContent = fmtMeta(data);
      updateSectionCounts();
      updateRoomSummary();
      if (svgEl) { body ? addRoomUnderline(svgEl, roomId) : removeRoomUnderline(svgEl, roomId); }
      status.textContent = body ? "Saved" : "Cleared";
      status.className = "room-save-status success";
      status.style.display = "inline";
      setTimeout(function () { status.style.display = "none"; }, 2500);
      if (!body) closeRoomCard(card);
    })
    .catch(function () {
      status.textContent = "Error saving";
      status.className = "room-save-status error";
      status.style.display = "inline";
    });
  }

  document.querySelectorAll(".room-card").forEach(function (card) {
    card.querySelector(".room-edit-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      openRoomCard(card);
      highlightMap(card.dataset.roomId);
    });
    card.querySelector(".room-save-btn").addEventListener("click", function () {
      saveRoomCard(card, card.querySelector(".room-note-input").value.trim());
    });
    card.querySelector(".room-clear-btn").addEventListener("click", function () {
      if (confirm("Clear the note for this room?")) saveRoomCard(card, "");
    });
    card.querySelector(".room-cancel-btn").addEventListener("click", function () {
      closeRoomCard(card);
    });
    card.querySelector(".room-note-input").addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
        saveRoomCard(card, card.querySelector(".room-note-input").value.trim());
      }
      if (e.key === "Escape") closeRoomCard(card);
    });
  });

  /* ══════════════════════════════════════════════════════════
     LOFT: zone notes
  ══════════════════════════════════════════════════════════ */
  function populateZoneNote(card) {
    var zoneId = card.dataset.zoneId;
    var note = notes[zoneId];
    var body = card.querySelector(".zone-note-body");
    var meta = card.querySelector(".zone-note-meta");
    if (note && note.body) {
      body.textContent = note.body;
      body.classList.remove("empty");
      if (meta) meta.textContent = fmtMeta(note);
    } else {
      body.textContent = "No note yet";
      body.classList.add("empty");
      if (meta) meta.textContent = "";
    }
  }

  document.querySelectorAll(".zone-card").forEach(function (card) {
    var zoneId = card.dataset.zoneId;

    card.querySelector(".zone-note-edit-btn").addEventListener("click", function (e) {
      e.stopPropagation();
      var editor = card.querySelector(".zone-note-editor");
      var view = card.querySelector(".zone-note-view");
      var note = notes[zoneId] || {};
      card.querySelector(".zone-note-input").value = note.body || "";
      card.querySelector(".zone-note-meta").textContent = fmtMeta(note);
      view.style.display = "none";
      editor.style.display = "block";
      card.querySelector(".zone-note-input").focus();
    });

    card.querySelector(".zone-note-cancel-btn").addEventListener("click", function () {
      card.querySelector(".zone-note-editor").style.display = "none";
      card.querySelector(".zone-note-view").style.display = "";
    });

    card.querySelector(".zone-note-save-btn").addEventListener("click", function () {
      var body = card.querySelector(".zone-note-input").value.trim();
      var status = card.querySelector(".zone-note-editor .save-status");
      status.style.display = "none";
      fetch(noteUrl(zoneId), {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRFToken": CSRF},
        body: JSON.stringify({body: body})
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        notes[zoneId] = data;
        populateZoneNote(card);
        card.querySelector(".zone-note-editor").style.display = "none";
        card.querySelector(".zone-note-view").style.display = "";
      })
      .catch(function () {
        status.textContent = "Error saving";
        status.className = "save-status error";
        status.style.display = "inline";
      });
    });
  });

  /* ══════════════════════════════════════════════════════════
     LOFT: item rendering + CRUD
  ══════════════════════════════════════════════════════════ */
  function renderItems(card) {
    var zoneId = card.dataset.zoneId;
    var items = loftItems[zoneId] || [];
    var list = card.querySelector(".loft-items-list");
    list.innerHTML = "";

    items.forEach(function (item) {
      var row = document.createElement("div");
      row.className = "loft-item-row";
      row.dataset.itemId = item.id;

      var body = document.createElement("div");
      body.className = "loft-item-body";

      var name = document.createElement("div");
      name.className = "loft-item-name";
      name.textContent = item.name;
      body.appendChild(name);

      if (item.description) {
        var desc = document.createElement("div");
        desc.className = "loft-item-desc";
        desc.textContent = item.description;
        body.appendChild(desc);
      }

      var meta = document.createElement("div");
      meta.className = "loft-item-meta";
      meta.textContent = "Added" + (item.added_by ? " by " + item.added_by : "") + " · " + fmtDate(item.added_at);
      body.appendChild(meta);

      // Photos
      var photos = document.createElement("div");
      photos.className = "loft-item-photos";
      (item.photos || []).forEach(function (p) {
        photos.appendChild(makePhotoThumb(p, item.id, zoneId));
      });

      // Upload button
      var uploadBtn = document.createElement("button");
      uploadBtn.className = "loft-photo-upload-btn";
      uploadBtn.title = "Add photo";
      uploadBtn.setAttribute("aria-label", "Upload photo for " + item.name);
      uploadBtn.textContent = "+";
      uploadBtn.addEventListener("click", function () {
        pendingPhotoUpload = {itemId: item.id, zoneId: zoneId};
        document.getElementById("photo-file-input").click();
      });
      photos.appendChild(uploadBtn);
      body.appendChild(photos);

      row.appendChild(body);

      // Delete item button
      var del = document.createElement("button");
      del.className = "btn btn-sm btn-outline-danger loft-item-delete-btn";
      del.textContent = "✕";
      del.setAttribute("aria-label", "Delete " + item.name);
      del.addEventListener("click", function () {
        if (!confirm('Delete "' + item.name + '" from the inventory?')) return;
        fetch(itemUrl(item.id), {
          method: "DELETE",
          headers: {"X-CSRFToken": CSRF}
        })
        .then(function (r) { return r.json(); })
        .then(function () {
          loftItems[zoneId] = loftItems[zoneId].filter(function (i) { return i.id !== item.id; });
          renderItems(card);
          updateLoftSummary();
        });
      });
      row.appendChild(del);

      list.appendChild(row);
    });

    if (items.length === 0) {
      var empty = document.createElement("p");
      empty.className = "text-muted mb-1";
      empty.style.fontSize = "0.8rem";
      empty.style.fontStyle = "italic";
      empty.textContent = "No items logged yet.";
      list.appendChild(empty);
    }
  }

  function makePhotoThumb(photo, itemId, zoneId) {
    var wrap = document.createElement("div");
    wrap.className = "loft-photo-thumb";
    var img = document.createElement("img");
    img.src = photo.url;
    img.alt = photo.caption || "Loft photo";
    img.loading = "lazy";
    wrap.appendChild(img);
    var del = document.createElement("button");
    del.className = "loft-photo-delete-btn";
    del.textContent = "✕";
    del.setAttribute("aria-label", "Delete photo");
    del.addEventListener("click", function () {
      if (!confirm("Delete this photo?")) return;
      fetch(photoDeleteUrl(photo.id), {
        method: "POST",
        headers: {"X-CSRFToken": CSRF}
      })
      .then(function (r) { return r.json(); })
      .then(function () {
        var item = (loftItems[zoneId] || []).find(function (i) { return i.id === itemId; });
        if (item) item.photos = item.photos.filter(function (p) { return p.id !== photo.id; });
        var card = document.querySelector('.zone-card[data-zone-id="' + zoneId + '"]');
        if (card) renderItems(card);
      });
    });
    wrap.appendChild(del);
    return wrap;
  }

  // Photo file input handler
  document.getElementById("photo-file-input").addEventListener("change", function (e) {
    var file = e.target.files[0];
    if (!file || !pendingPhotoUpload) return;
    var p = pendingPhotoUpload;
    pendingPhotoUpload = null;
    e.target.value = "";
    var fd = new FormData();
    fd.append("image", file);
    fetch(itemPhotoUrl(p.itemId), {
      method: "POST",
      headers: {"X-CSRFToken": CSRF},
      body: fd
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) { alert("Upload failed: " + data.error); return; }
      var item = (loftItems[p.zoneId] || []).find(function (i) { return i.id === p.itemId; });
      if (item) item.photos.push(data);
      var card = document.querySelector('.zone-card[data-zone-id="' + p.zoneId + '"]');
      if (card) renderItems(card);
    })
    .catch(function () { alert("Upload failed."); });
  });

  // Add item form
  document.querySelectorAll(".zone-card").forEach(function (card) {
    var zoneId = card.dataset.zoneId;

    card.querySelector(".item-new-btn").addEventListener("click", function () {
      card.querySelector(".item-add-form").style.display = "block";
      card.querySelector(".item-new-btn").style.display = "none";
      card.querySelector(".item-name-input").focus();
    });

    card.querySelector(".item-cancel-btn").addEventListener("click", function () {
      card.querySelector(".item-add-form").style.display = "none";
      card.querySelector(".item-new-btn").style.display = "";
      card.querySelector(".item-name-input").value = "";
      card.querySelector(".item-desc-input").value = "";
    });

    card.querySelector(".item-save-btn").addEventListener("click", function () {
      var name = card.querySelector(".item-name-input").value.trim();
      if (!name) { card.querySelector(".item-name-input").focus(); return; }
      var desc = card.querySelector(".item-desc-input").value.trim();
      var status = card.querySelector(".item-add-form .save-status");
      status.style.display = "none";
      fetch(itemCreateUrl(zoneId), {
        method: "POST",
        headers: {"Content-Type": "application/json", "X-CSRFToken": CSRF},
        body: JSON.stringify({name: name, description: desc})
      })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (data.error) throw new Error(data.error);
        if (!loftItems[zoneId]) loftItems[zoneId] = [];
        loftItems[zoneId].push(data);
        renderItems(card);
        updateLoftSummary();
        card.querySelector(".item-add-form").style.display = "none";
        card.querySelector(".item-new-btn").style.display = "";
        card.querySelector(".item-name-input").value = "";
        card.querySelector(".item-desc-input").value = "";
      })
      .catch(function () {
        status.textContent = "Error adding item";
        status.className = "save-status error";
        status.style.display = "inline";
      });
    });
  });

  function updateLoftSummary() {
    var total = 0;
    Object.values(loftItems).forEach(function (items) { total += items.length; });
    var el = document.getElementById("loft-summary");
    el.textContent = total === 0
      ? "No items logged yet. Use the zone cards below to document what’s in the loft."
      : total + " item" + (total === 1 ? "" : "s") + " logged across all zones.";
  }

  /* ══════════════════════════════════════════════════════════
     AREA PHOTOS
  ══════════════════════════════════════════════════════════ */
  function renderAreaPhoto(container, areaId) {
    container.innerHTML = "";
    var photo = areaPhotos[areaId];
    if (photo) {
      var wrap = document.createElement("div");
      wrap.className = "area-photo-wrap";
      wrap.addEventListener("click", function () { window.open(photo.url, "_blank"); });
      var img = document.createElement("img");
      img.src = photo.url;
      img.alt = "Photo of area";
      img.className = "area-photo-img";
      img.loading = "lazy";
      wrap.appendChild(img);
      var overlay = document.createElement("div");
      overlay.className = "area-photo-overlay";
      var changeBtn = document.createElement("button");
      changeBtn.className = "area-photo-action-btn";
      changeBtn.textContent = "Change";
      changeBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        pendingAreaPhotoId = areaId;
        document.getElementById("area-photo-input").click();
      });
      var delBtn = document.createElement("button");
      delBtn.className = "area-photo-action-btn";
      delBtn.style.color = "#dc3545";
      delBtn.textContent = "Delete";
      delBtn.addEventListener("click", function (e) {
        e.stopPropagation();
        e.preventDefault();
        if (!confirm("Delete the photo for this area?")) return;
        fetch(areaPhotoDeleteUrl(areaId), {
          method: "POST",
          headers: {"X-CSRFToken": CSRF}
        })
        .then(function (r) { return r.json(); })
        .then(function () {
          delete areaPhotos[areaId];
          document.querySelectorAll(".area-photo-container").forEach(function (c) {
            var el = c.closest("[data-room-id], [data-zone-id]");
            if (el) {
              var id = el.dataset.roomId || el.dataset.zoneId;
              if (id === areaId) renderAreaPhoto(c, areaId);
            }
          });
        });
      });
      overlay.appendChild(changeBtn);
      overlay.appendChild(delBtn);
      wrap.appendChild(overlay);
      container.appendChild(wrap);
    } else {
      var btn = document.createElement("button");
      btn.className = "area-photo-upload-btn";
      btn.setAttribute("aria-label", "Add photo for this area");
      btn.innerHTML = "&#128247; Add photo";
      btn.addEventListener("click", function () {
        pendingAreaPhotoId = areaId;
        document.getElementById("area-photo-input").click();
      });
      container.appendChild(btn);
    }
  }

  function populateAllAreaPhotos() {
    document.querySelectorAll(".area-photo-container").forEach(function (container) {
      var el = container.closest("[data-room-id], [data-zone-id]");
      if (!el) return;
      var areaId = el.dataset.roomId || el.dataset.zoneId;
      renderAreaPhoto(container, areaId);
    });
  }

  document.getElementById("area-photo-input").addEventListener("change", function (e) {
    var file = e.target.files[0];
    if (!file || !pendingAreaPhotoId) return;
    var areaId = pendingAreaPhotoId;
    pendingAreaPhotoId = null;
    e.target.value = "";
    var fd = new FormData();
    fd.append("image", file);
    fetch(areaPhotoUrl(areaId), {
      method: "POST",
      headers: {"X-CSRFToken": CSRF},
      body: fd
    })
    .then(function (r) { return r.json(); })
    .then(function (data) {
      if (data.error) { alert("Upload failed: " + data.error); return; }
      areaPhotos[areaId] = data;
      document.querySelectorAll(".area-photo-container").forEach(function (c) {
        var el = c.closest("[data-room-id], [data-zone-id]");
        if (el) {
          var id = el.dataset.roomId || el.dataset.zoneId;
          if (id === areaId) renderAreaPhoto(c, areaId);
        }
      });
    })
    .catch(function () { alert("Upload failed."); });
  });

  /* ══════════════════════════════════════════════════════════
     SVG: load + wire up both room and zone interaction
  ══════════════════════════════════════════════════════════ */
  function highlightMap(id) {
    if (!svgEl) return;
    if (selectedMapId) {
      var prev = svgEl.getElementById(selectedMapId);
      if (prev) prev.classList.remove("map-selected");
    }
    selectedMapId = id;
    var el = svgEl.getElementById(id);
    if (el) el.classList.add("map-selected");
  }

  function getLabelEl(roomId) {
    return svgEl ? svgEl.getElementById(roomId.replace(/^room-/, "label-")) : null;
  }
  function underlineId(roomId) { return "note-ul-" + roomId; }

  function addRoomUnderline(svg, roomId) {
    if (svg.getElementById(underlineId(roomId))) return;
    var label = getLabelEl(roomId);
    if (!label) return;
    var bbox = label.getBBox();
    var bar = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    bar.setAttribute("id", underlineId(roomId));
    bar.setAttribute("x", bbox.x);
    bar.setAttribute("y", bbox.y + bbox.height + 4);
    bar.setAttribute("width", bbox.width);
    bar.setAttribute("height", Math.max(3, bbox.height * 0.06));
    bar.setAttribute("fill", "#000");
    bar.setAttribute("pointer-events", "none");
    label.parentNode.insertBefore(bar, label.nextSibling);
  }

  function removeRoomUnderline(svg, roomId) {
    var el = svg.getElementById(underlineId(roomId));
    if (el) el.parentNode.removeChild(el);
  }

  function selectFromMap(id) {
    highlightMap(id);
    var isLoft = id.indexOf("loft-") === 0;
    var selector = isLoft
      ? '.zone-card[data-zone-id="' + id + '"]'
      : '.room-card[data-room-id="' + id + '"]';
    var card = document.querySelector(selector);
    if (!card) return;
    if (isLoft) {
      document.querySelectorAll(".zone-card").forEach(function (c) { c.classList.remove("zone-selected"); });
      card.classList.add("zone-selected");
    } else {
      document.querySelectorAll(".room-card").forEach(function (c) { c.classList.remove("room-selected"); });
      card.classList.add("room-selected");
      openRoomCard(card);
    }
    card.scrollIntoView({behavior: "smooth", block: "center"});
  }

  fetch(svgUrl)
    .then(function (r) { return r.text(); })
    .then(function (svgText) {
      var container = document.getElementById("floorplan-container");
      container.innerHTML = svgText;
      svgEl = container.querySelector("svg");
      svgEl.removeAttribute("width");
      svgEl.removeAttribute("height");
      svgEl.setAttribute("preserveAspectRatio", "xMidYMid meet");

      // Apply layer visibility based on whichever tab is already active
      var layer3 = svgEl.getElementById("layer3");
      var layer4 = svgEl.getElementById("layer4");
      var layer5 = svgEl.getElementById("layer5");
      if (layer3) layer3.style.display = activeTab === "groundfloor" ? "inline" : "none";
      if (layer4) layer4.style.display = activeTab === "groundfloor" ? "inline" : "none";
      if (layer5) layer5.style.display = activeTab === "loft" ? "inline" : "none";

      // Underline rooms that already have notes
      Object.keys(notes).forEach(function (roomId) {
        if (notes[roomId].body && roomId.indexOf("loft-") !== 0) {
          addRoomUnderline(svgEl, roomId);
        }
      });

      function getTitle(el) {
        var t = el.querySelector("title");
        return t ? t.textContent.trim() : el.id.replace(/^(room|loft)-/, "").replace(/-/g, " ");
      }

      // Wire ground floor rooms
      svgEl.querySelectorAll("[id^='room-']").forEach(function (el) {
        el.setAttribute("tabindex", "0");
        el.setAttribute("role", "button");
        el.setAttribute("aria-label", getTitle(el));
        el.addEventListener("click", function () { selectFromMap(el.id); });
        el.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") { e.preventDefault(); selectFromMap(el.id); }
        });
      });
      svgEl.querySelectorAll("[id^='label-']:not([id^='label-loft'])").forEach(function (labelEl) {
        var roomId = labelEl.id.replace(/^label-/, "room-");
        if (!svgEl.getElementById(roomId)) return;
        labelEl.style.cursor = "pointer";
        labelEl.addEventListener("click", function () { selectFromMap(roomId); });
      });

      // Wire loft zones
      svgEl.querySelectorAll("[id^='loft-']:not([id^='loft-entry'])").forEach(function (el) {
        if (!el.dataset.zone) return;
        el.addEventListener("click", function () {
          if (activeTab !== "loft") switchTab("loft");
          selectFromMap(el.id);
        });
        el.addEventListener("keydown", function (e) {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            if (activeTab !== "loft") switchTab("loft");
            selectFromMap(el.id);
          }
        });
      });
      svgEl.querySelectorAll("[id^='label-loft']").forEach(function (labelEl) {
        var zoneId = labelEl.id.replace(/^label-/, "");
        if (!svgEl.getElementById(zoneId)) return;
        labelEl.style.cursor = "pointer";
        labelEl.addEventListener("click", function () {
          if (activeTab !== "loft") switchTab("loft");
          selectFromMap(zoneId);
        });
      });
    })
    .catch(function () {
      document.getElementById("floorplan-loading").textContent = "Failed to load map.";
    });

  /* ══════════════════════════════════════════════════════════
     INITIALISE
  ══════════════════════════════════════════════════════════ */
  populateAllRooms();
  document.querySelectorAll(".zone-card").forEach(function (card) {
    populateZoneNote(card);
    renderItems(card);
  });
  updateLoftSummary();
  populateAllAreaPhotos();

  // Restore tab from URL hash
  if (window.location.hash === "#loft") switchTab("loft");
  document.getElementById("tab-groundfloor-btn").addEventListener("click", function () {
    history.replaceState(null, "", window.location.pathname);
  });
  document.getElementById("tab-loft-btn").addEventListener("click", function () {
    history.replaceState(null, "", window.location.pathname + "#loft");
  });
}
