// Interference check harness for sweep.py. Copy next to the model, adjust.
//
// The model file must (a) put its top-level `if (part == ...)` dispatch behind
// a `part` variable so that including it with part="none" draws nothing, and
// (b) expose the pose maths (angles, link positions) as functions of the
// sweep variable, the same ones montaje() uses. Then posed(name) below places
// each part exactly as the assembly view does, and sweep.py intersects pairs.
include <MODEL.scad>
part = "none";

A = "casa"; B = "tablero"; crank = 0;        // set by sweep.py with -D

// --- pose of everything at this crank value: copy from montaje() ---------
psi_c = psi_min + crank * 360 / gear_z;
th_c  = deck_angle(psi_c);

module posed(n) {
    if (n == "casa")    casa();
    if (n == "tablero") translate([0, 0, piv_z]) rotate([0, -th_c, 0]) translate([0, 0, -piv_z]) tablero();
    // ... one line per part, same transforms as montaje() ...
    // A big slab under the model catches anything that dips below the floor:
    if (n == "suelo")   translate([-500, -500, -20]) cube([1000, 1000, 20]);
}

intersection() { posed(A); posed(B); }
