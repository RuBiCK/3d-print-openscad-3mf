// Wooden train track (BRIO / IKEA LILLABO / Hape / Aldi clones) -- shared library
// -------------------------------------------------------------------------
// Every dimension here was MEASURED on meshes of real pieces, not estimated:
//   track section  : jointbrio_3pcs.3mf (12.000 thick), ramp-wood-train-brio-ikea-aldi.3mf
//                    (39.806 wide, grooves 5.4 wide at +-13.0)
//   male connector : jointbrio_3pcs.3mf
//   female socket  : wood-train-turnplate-less-mats.3mf
//   ramp rise      : ramp-wood-train-brio-ikea-aldi.3mf, 64.7 mm over 216 mm
// See domains/wooden-train.md for the rules (how pieces connect, what a train
// needs to pass under, how a pillar should be a piece of track).
//
//   use <lib/wooden_train.scad>;   // relative to the skill root; or copy it next to your model
//   wt_straight(216);                       // a straight, male at +X, female at -X
//   linear_extrude(wt_track_h) wt_male_2d();   // just the peg, at the origin, pointing +X
//   wt_grooves(x0, x1);                     // subtract: the two wheel-flange grooves

/* [Track section] */
wt_track_w  = 40.0;   // measured 39.8; modelled at 40
wt_track_h  = 12.0;
wt_groove_w =  6.0;   // measured 5.4; 6.0 so wheels never bind
wt_groove_d =  3.0;
wt_groove_c = 13.0;   // groove centres at +-13

/* [Male connector: neck, then a round head] */
wt_peg_neck   =  6.0;   // neck width
wt_peg_head_c = 11.0;   // head centre from the face
wt_peg_head_d = 12.0;
wt_peg_len    = 17.0;   // head is cut flat at 17
wt_peg_slack  =  0.0;   // set negative (-0.2) if the peg is tight in your tracks

/* [Female socket: funnel mouth, straight neck, round chamber] */
wt_sock_mouth  = 15.4;
wt_sock_funnel =  2.5;  // funnel depth
wt_sock_neck   =  7.3;  // narrower than the head: the peg DROPS in from above
wt_sock_c      = 11.1;  // chamber centre from the face
wt_sock_cham_d = 12.8;  // chamber diameter (12.7 measured)

/* [Layout constants] */
wt_ramp_rise   = 65.0;  // one standard ramp lifts the track this much (64.7 measured)
wt_ramp_len    = 216.0; // between connector faces; same as a long straight "D"
wt_train_clear = 60.0;  // free height a bridge should leave over the floor for a train on a track

// ---- 2D profiles, at the origin, connector pointing +X ------------------
module wt_male_2d(slack = wt_peg_slack) {
    intersection() {
        union() {
            translate([0, -(wt_peg_neck + slack) / 2]) square([wt_peg_head_c, wt_peg_neck + slack]);
            translate([wt_peg_head_c, 0]) circle(d = wt_peg_head_d + slack, $fn = 64);
        }
        translate([0, -20]) square([wt_peg_len, 40]);
    }
}
// the socket is a THROUGH slot over the full track thickness: extrude it wt_track_h
module wt_female_2d(slack = 0) {
    offset(r = slack / 2) union() {
        polygon([[-0.01,  wt_sock_mouth / 2], [wt_sock_funnel,  wt_sock_neck / 2],
                 [wt_sock_funnel, -wt_sock_neck / 2], [-0.01, -wt_sock_mouth / 2]]);
        translate([-0.01, -wt_sock_neck / 2]) square([wt_sock_c + 0.01, wt_sock_neck]);
        translate([wt_sock_c, 0]) circle(d = wt_sock_cham_d, $fn = 64);
    }
}
// 45 degree funnel around the socket mouth, to subtract from the top face:
// lets a peg that arrives from above (a lifting deck, a loosely placed
// pillar) centre itself. depth in mm.
module wt_female_funnel(depth = 2, slack = 0) {
    translate([0, 0, wt_track_h - depth]) minkowski() {
        linear_extrude(0.01) wt_female_2d(slack);
        cylinder(h = depth + 0.01, r1 = 0.01, r2 = depth, $fn = 32);
    }
}

// ---- solids ---------------------------------------------------------------
// wheel grooves, to subtract; x0..x1 along the track
module wt_grooves(x0, x1) {
    for (m = [-1, 1])
        translate([x0 - 0.01, m * wt_groove_c - wt_groove_w / 2, wt_track_h - wt_groove_d])
            cube([x1 - x0 + 0.02, wt_groove_w, wt_groove_d + 0.01]);
}
// straight piece: body from x=0 to len (connector faces), female at 0, male beyond len
module wt_straight(len, male = true, female = true) {
    difference() {
        union() {
            translate([0, -wt_track_w / 2, 0]) cube([len, wt_track_w, wt_track_h]);
            if (male) translate([len, 0, 0]) linear_extrude(wt_track_h) wt_male_2d();
        }
        if (female) translate([0, 0, -0.01]) linear_extrude(wt_track_h + 0.02) wt_female_2d();
        wt_grooves(-1, len + wt_peg_len + 1);
    }
}
// side guides with a lead-in chamfer, for a platform a track end rests on.
// Only where the neighbour is a straight: a curve needs the platform flat.
module wt_guides(len, fit = 0.8, t = 3, h = 6, cham = 2) {
    for (m = [-1, 1]) mirror([0, m < 0 ? 1 : 0, 0])
        translate([0, (wt_track_w + fit) / 2, 0]) rotate([90, 0, 90])
            linear_extrude(len) polygon([[0, 0], [t, 0], [t, h], [cham, h], [0, h - cham]]);
}
