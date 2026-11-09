// human-contributors: ["Jonny Kram"]; ai-contributors: ["Claude Opus 5.5"]; status: "#ai-written"
// Public seat views page (9.176): draws the seating plan as SVG and shows the
// photo for whichever seat is picked. Seats without a photo of their own show
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
                tabindex: 0,
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
            seats.push({ id: id, name: name, photo: photo, x: s.x, y: cy / PITCH, g: g });
        });
        y += ROW_GAP;
    });

    el("rect", { x: LEFT - R, y: y + 10, width: 10 * PITCH + R * 2, height: 34, rx: 4, class: "seat-views__screen" }, svg);
    el("text", { x: LEFT + 5 * PITCH, y: y + 33, "text-anchor": "middle", class: "seat-views__screen-label" }, svg).textContent = "SCREEN";
    svg.setAttribute("viewBox", "0 0 " + (LEFT + 11 * PITCH) + " " + (y + 54));

    // A seat with no photo of its own borrows the closest photographed seat,
    // by straight-line distance on the plan.
    var withPhotos = seats.filter(function (s) { return s.photo; });
    function nearest(seat) {
        var dist = function (s) { return Math.hypot(s.x - seat.x, s.y - seat.y); };
        return withPhotos.reduce(function (best, s) { return dist(s) < dist(best) ? s : best; });
    }

    var lowerFirst = function (s) { return s.charAt(0).toLowerCase() + s.slice(1); };

    function select(seat, updateHash) {
        seats.forEach(function (s) {
            s.g.classList.remove("seat-views__seat--selected", "seat-views__seat--source");
        });
        seat.g.classList.add("seat-views__seat--selected");
        var source = seat.photo ? seat : nearest(seat);
        if (source !== seat) { source.g.classList.add("seat-views__seat--source"); }

        opts.title.textContent = seat.name;
        var img = new Image();
        img.className = "seat-views__photo";
        img.src = opts.photos[source.photo];
        img.alt = "View of the screen from " + lowerFirst(source.name);
        opts.media.replaceChildren(img);
        opts.note.textContent = source === seat
            ? "Photo taken from this seat."
            : "No photo from this exact seat yet. This is the view from " + lowerFirst(source.name)
              + ", the nearest one (dashed outline).";
        if (updateHash) { history.replaceState(null, "", "#" + seat.id); }
    }

    if (!withPhotos.length) { return; }

    seats.forEach(function (seat) {
        seat.g.addEventListener("click", function () { select(seat, true); });
        seat.g.addEventListener("keydown", function (e) {
            if (e.key === "Enter" || e.key === " ") { e.preventDefault(); select(seat, true); }
        });
    });

    // Deep links like /labs/seat-views/#C5 open with that seat selected.
    var hashId = decodeURIComponent(location.hash.slice(1));
    var fromHash = seats.filter(function (s) { return s.id === hashId; })[0];
    if (fromHash) { select(fromHash, false); }
}
