// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 5.5"]; status: "#ai-written"
// Public seat views page (9.176): draws the seating plan as SVG and shows the
// photo for whichever seat is picked (by click or tap anywhere on the plan,
// snapping to the nearest seat, or by arrow keys). Seats without a photo of their own show
// the nearest photographed seat's view instead, with that seat outlined.
// Called once from labs/seat_views.html with the page's elements and a
// { seatId: url } map of the photos that exist.

function seatViews(opts) {
    "use strict";

    // Seat positions in column units, transcribed from the box office
    // (Ticketsolve) seating plan. Some rows are offset by half a seat; row E
    // has gaps and two wheelchair spaces.
    var run = function (n, offset) {
        var seats = [];
        for (var i = 0; i < n; i++) {
            seats.push({ n: String(i + 1), x: i + 1 + (offset || 0) });
        }
        return seats;
    };
    var ROWS = [
        { row: "I", seats: run(11) },
        { row: "H", seats: run(11, 0.5) },
        { row: "G", seats: run(11) },
        { row: "F", seats: run(10, 0.5) },
        { row: "E", aisleBefore: true, seats: [
            { n: "1", x: 1 }, { n: "2", x: 2 }, { wc: "left", x: 3 },
            { n: "5", x: 6 }, { n: "6", x: 7 },
            { wc: "right", x: 9 }, { n: "10", x: 10 }, { n: "11", x: 11 },
        ] },
        { row: "D", seats: run(11) },
        { row: "C", seats: run(10, 0.5) },
        { row: "B", seats: run(11) },
        // The plan ends row A with a wheelchair space, not a seat A11; the
        // A11 photo was taken from that space.
        { row: "A", seats: run(9, 0.5).concat([{ wc: "end", x: 10.5, photo: "A11" }]) },
        { row: "COMFY", label: "Comfy", aisleBefore: true, seats: [
            { n: "1", x: 1 }, { n: "2", x: 2 }, { n: "3", x: 3 }, { n: "4", x: 5 },
            { n: "5", x: 7 }, { n: "6", x: 10 }, { n: "7", x: 11 },
        ] },
    ];

    var PITCH = 40, ROW_GAP = 42, AISLE = 30, LEFT = 70, TOP = 24, R = 15;
    var NS = "http://www.w3.org/2000/svg";
    var svg = opts.svg;
    var seats = [];

    function el(tag, attrs, parent) {
        var e = document.createElementNS(NS, tag);
        Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
        parent.appendChild(e);
        return e;
    }

    function seatName(row, label, s) {
        if (s.wc) {
            return "Wheelchair space, row " + (label || row) + (s.wc === "end" ? "" : ", " + s.wc);
        }
        return (label ? label + " seat " : "Row " + row + ", seat ") + s.n;
    }

    // Faint wedge from the chosen seat to the two edges of the screen, drawn
    // first so it sits underneath the seats.
    var sightline = el("polygon", { class: "seat-views__sightline", points: "" }, svg);

    var y = TOP;
    ROWS.forEach(function (r) {
        if (r.aisleBefore) { y += AISLE; }
        var cy = y + R;
        el("text", { x: 8, y: cy + 5, class: "seat-views__row-label" }, svg).textContent = r.label || r.row;
        r.seats.forEach(function (s) {
            var cx = LEFT + (s.x - 1) * PITCH;
            var id = s.wc ? r.row + "-wc-" + s.wc : r.row + s.n;
            var photoId = s.photo || id;
            var photo = opts.photos[photoId] ? photoId : null;
            var name = seatName(r.row, r.label, s);
            var g = el("g", {
                class: "seat-views__seat" + (photo ? " seat-views__seat--photo" : ""),
                tabindex: -1,
                role: "button",
                "aria-label": name + (photo ? " (photo)" : ""),
            }, svg);
            if (s.wc) {
                el("rect", { x: cx - R, y: cy - R, width: R * 2, height: R * 2, rx: 3 }, g);
                el("text", { x: cx, y: cy + 5, "text-anchor": "middle" }, g).textContent = "♿";
            } else {
                el("circle", { cx: cx, cy: cy, r: R }, g);
                el("text", { x: cx, y: cy + 4.5, "text-anchor": "middle" }, g).textContent = s.n;
            }
            seats.push({ id: id, name: name, photo: photo, x: s.x, y: cy / PITCH, cx: cx, cy: cy, row: r.row, g: g });
        });
        y += ROW_GAP;
    });

    el("rect", { x: LEFT - R, y: y + 10, width: 10 * PITCH + R * 2, height: 34, rx: 4, class: "seat-views__screen" }, svg);
    el("text", { x: LEFT + 5 * PITCH, y: y + 33, "text-anchor": "middle", class: "seat-views__screen-label" }, svg).textContent = "SCREEN";
    svg.setAttribute("viewBox", "0 0 " + (LEFT + 11 * PITCH) + " " + (y + 54));
    var screenY = y + 10, screenL = LEFT - R, screenR = LEFT + 10 * PITCH + R;

    // A seat with no photo of its own borrows the closest photographed seat,
    // by straight-line distance on the plan.
    var withPhotos = seats.filter(function (s) { return s.photo; });
    function nearest(seat) {
        var dist = function (s) { return Math.hypot(s.x - seat.x, s.y - seat.y); };
        return withPhotos.reduce(function (best, s) { return dist(s) < dist(best) ? s : best; });
    }

    var lowerFirst = function (s) { return s.charAt(0).toLowerCase() + s.slice(1); };

    var current = null;

    function select(seat, updateHash) {
        seats.forEach(function (s) {
            s.g.classList.remove("seat-views__seat--selected", "seat-views__seat--source");
            s.g.setAttribute("tabindex", -1);
        });
        seat.g.classList.add("seat-views__seat--selected");
        seat.g.setAttribute("tabindex", 0);
        current = seat;
        sightline.setAttribute("points", [seat.cx, seat.cy, screenL, screenY, screenR, screenY].join(" "));
        var source = seat.photo ? seat : nearest(seat);
        if (source !== seat) { source.g.classList.add("seat-views__seat--source"); }

        opts.title.textContent = seat.name;
        var img = new Image();
        img.className = "seat-views__photo";
        img.src = opts.photos[source.photo];
        img.alt = "View of the screen from " + lowerFirst(source.name);
        opts.media.replaceChildren(img);
        opts.note.textContent = source === seat
            ? "Taken from this seat."
            : "We don't have a photo from this seat yet, so this one is from "
              + lowerFirst(source.name) + " (dashed outline), the nearest we have.";
        if (updateHash) {
            history.replaceState(null, "", "#" + seat.id);
            // On a phone the photo can be scrolled out of sight while you tap
            // the plan; bring it back.
            var box = opts.preview.getBoundingClientRect();
            if (box.top < 0 || box.top > window.innerHeight * 0.6) {
                opts.preview.scrollIntoView({ behavior: "smooth", block: "start" });
            }
        }
    }

    if (!withPhotos.length) { return; }

    // Clicking anywhere on the plan, not just on a seat, picks the seat
    // nearest to that point, so near misses on a phone still land.
    function seatAt(evt) {
        var pt = svg.createSVGPoint();
        pt.x = evt.clientX;
        pt.y = evt.clientY;
        var p = pt.matrixTransform(svg.getScreenCTM().inverse());
        return seats.reduce(function (best, s) {
            var d = Math.hypot(s.cx - p.x, s.cy - p.y);
            return d < best.d ? { s: s, d: d } : best;
        }, { s: null, d: Infinity }).s;
    }

    svg.addEventListener("click", function (e) { select(seatAt(e), true); });

    // With a mouse, show which seat a click would pick.
    var hovered = null;
    svg.addEventListener("pointermove", function (e) {
        if (e.pointerType !== "mouse") { return; }
        var s = seatAt(e);
        if (s === hovered) { return; }
        if (hovered) { hovered.g.classList.remove("seat-views__seat--hover"); }
        hovered = s;
        s.g.classList.add("seat-views__seat--hover");
    });
    svg.addEventListener("pointerleave", function () {
        if (hovered) { hovered.g.classList.remove("seat-views__seat--hover"); }
        hovered = null;
    });

    // Keyboard: one tab stop for the whole plan, arrow keys to move around it.
    function step(dx, dy) {
        if (!current) { return null; }
        var rowsOrder = ROWS.map(function (r) { return r.row; });
        if (dx) {
            var row = seats.filter(function (s) { return s.row === current.row; });
            return row[row.indexOf(current) + dx] || null;
        }
        var next = rowsOrder[rowsOrder.indexOf(current.row) + dy];
        var candidates = seats.filter(function (s) { return s.row === next; });
        return candidates.reduce(function (best, s) {
            return !best || Math.abs(s.x - current.x) < Math.abs(best.x - current.x) ? s : best;
        }, null);
    }
    var KEYS = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] };
    svg.addEventListener("keydown", function (e) {
        var move = KEYS[e.key];
        if (!move) { return; }
        e.preventDefault();
        var s = step(move[0], move[1]);
        if (s) { select(s, true); s.g.focus(); }
    });

    // Deep links like /labs/seat-views/#C5 open with that seat selected;
    // otherwise start somewhere in the middle so the page is never empty.
    var hashId = decodeURIComponent(location.hash.slice(1));
    var byId = function (id) { return seats.filter(function (s) { return s.id === id; })[0]; };
    select(byId(hashId) || byId(opts.start) || withPhotos[0], false);
}
