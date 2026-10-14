// =====================================================================================
//  Carcasa de la planta: incubadora de yogur (Laboratorio de Supervisión, UMNG)
//  Imprimir en PETG (o ASA/ABS). NO usar PLA: se ablanda cerca de 55-60 °C.
//  Exportar cada parte:
//    openscad -D 'parte="base"'       -o base.stl       incubadora.scad
//    openscad -D 'parte="tapa"'       -o tapa.stl       incubadora.scad
//    openscad -D 'parte="bandeja"'    -o bandeja.stl    incubadora.scad
//    openscad -D 'parte="soporte_ventilador"' -o soporte_ventilador.stl incubadora.scad
//  Impresión sugerida: capa 0,24 mm, 4 perímetros, relleno 25 % giroide, sin soportes
//  (la base se imprime boca arriba; la tapa con el texto hacia arriba).
// =====================================================================================

parte = "ensamble";     // base | tapa | bandeja | soporte_ventilador | ensamble

// ---- Dimensiones interiores de la cámara [mm] ----
L = 160;  W = 120;  H = 120;
e = 2.4;              // espesor de pared
piso = 3;             // espesor del piso
r = 6;                // radio de esquinas exteriores
grupo = "GRUPO X";    // texto en la tapa

// ---- Componentes ----
placa = [100, 80];            // placa de aluminio del calefactor (2 x RH25 15 ohm)
separadores = [90, 70];       // separadores de latón M3 x 15 (no apoyar la placa caliente en plástico)
d_rtd = 7;                    // vaina de la RTD
d_prensa = 15.5;              // prensaestopa PG9
ksd_sep = 24;                 // KSD301: distancia entre agujeros de fijación
z_bandeja = 60;               // altura de los rieles de la bandeja
$fn = 48;

Lx = L + 2*e;  Wy = W + 2*e;

module caja_redondeada(x, y, z, rr) {
    hull() for (i = [rr, x-rr], j = [rr, y-rr]) translate([i, j, 0]) cylinder(r=rr, h=z);
}

module base() {
    difference() {
        union() {
            difference() {
                caja_redondeada(Lx, Wy, H + piso, r);
                translate([e, e, piso]) caja_redondeada(L, W, H + 1, max(r - e, 1));
            }
            // torres de esquina para insertos M3 de la tapa
            for (i = [e + 5, Lx - e - 5], j = [e + 5, Wy - e - 5])
                translate([i, j, 0]) cylinder(d=10, h=H + piso);
            // rieles para la bandeja (lados largos)
            for (j = [e, Wy - e - 4])
                translate([e + 8, j, piso + z_bandeja - 4]) cube([L - 16, 4, 4]);
            // manguito exterior de la RTD (pared derecha, a la altura del producto)
            translate([Lx, Wy/2, piso + z_bandeja + 25]) rotate([0, 90, 0]) cylinder(d=16, h=12);
            // patas
            for (i = [15, Lx - 15], j = [15, Wy - 15]) translate([i, j, -4]) cylinder(d=14, h=4);
        }
        // insertos roscados M3 (d = 4,2 mm, 6 mm de profundidad)
        for (i = [e + 5, Lx - e - 5], j = [e + 5, Wy - e - 5])
            translate([i, j, H + piso - 6]) cylinder(d=4.2, h=7);
        // agujeros para separadores de la placa calefactora
        for (i = [-1, 1], j = [-1, 1])
            translate([Lx/2 + i*separadores[0]/2, Wy/2 + j*separadores[1]/2, -5]) cylinder(d=3.4, h=20);
        // paso de la RTD
        translate([Lx - e - 1, Wy/2, piso + z_bandeja + 25]) rotate([0, 90, 0]) cylinder(d=d_rtd, h=20);
        // prensaestopa de cables (pared trasera, abajo)
        translate([Lx/2, Wy + 1, piso + 18]) rotate([90, 0, 0]) cylinder(d=d_prensa, h=e + 2);
        // fijación del termostato KSD301 (pared izquierda, arriba)
        for (k = [-1, 1])
            translate([-1, Wy/2 + k*ksd_sep/2, piso + H - 18]) rotate([0, 90, 0]) cylinder(d=3.4, h=e + 2);
        // fijación del soporte del ventilador (piso)
        for (k = [-1, 1])
            translate([e + 20 + k*10, Wy/2, -5]) cylinder(d=3.4, h=20);
        // ventana para el LED del calefactor (frontal)
        translate([Lx/2, -1, piso + 10]) rotate([-90, 0, 0]) cylinder(d=5.2, h=e + 2);
        // texto en el frente
        translate([Lx/2, 0.6, piso + H/2]) rotate([90, 0, 0])
            linear_extrude(1) text("INCUBADORA", size=9, halign="center", valign="center", font="Liberation Sans:style=Bold");
    }
}

module tapa() {
    difference() {
        union() {
            caja_redondeada(Lx, Wy, 3, r);
            // labio que entra en la cámara (con 0,4 mm de holgura)
            translate([e + 0.4, e + 0.4, -6]) difference() {
                caja_redondeada(L - 0.8, W - 0.8, 6, max(r - e, 1));
                translate([2, 2, -1]) caja_redondeada(L - 4.8, W - 4.8, 8, max(r - e - 2, 1));
            }
            // manija
            translate([Lx/2 - 35, Wy/2 - 6, 3]) difference() {
                cube([70, 12, 22]);
                translate([10, -1, -1]) cube([50, 14, 16]);
            }
            // texto
            translate([Lx/2, 22, 3]) linear_extrude(0.8)
                text(grupo, size=10, halign="center", font="Liberation Sans:style=Bold");
        }
        // tornillos M3 avellanados
        for (i = [e + 5, Lx - e - 5], j = [e + 5, Wy - e - 5]) {
            translate([i, j, -10]) cylinder(d=3.4, h=20);
            translate([i, j, 1.2]) cylinder(d1=3.4, d2=7, h=1.9);
        }
        // recorte del labio en las torres de esquina
        for (i = [e + 5, Lx - e - 5], j = [e + 5, Wy - e - 5])
            translate([i, j, -7]) cylinder(d=11, h=7);
    }
}

module bandeja() {
    // bandeja perforada para los vasos de yogur; apoya en los rieles
    bx = L - 2;  by = W - 2;
    difference() {
        cube([bx, by, 2.4]);
        for (i = [12:14:bx - 10], j = [12:14:by - 10]) translate([i, j, -1]) cylinder(d=8, h=5);
        for (i = [0, bx]) translate([i, by/2, -1]) cylinder(d=30, h=5);  // agarres
        for (i = [0, bx - 12], j = [0, by - 12]) translate([i, j, -1]) cube([12, 12, 5]);  // torres
    }
}

module soporte_ventilador() {
    // escuadra para ventilador de 40 mm (agujeros a 32 mm), atornillada al piso
    difference() {
        union() {
            cube([44, 30, 3]);
            translate([0, 0, 0]) cube([44, 3, 50]);
        }
        translate([22, 1.5, 28]) rotate([90, 0, 0]) cylinder(d=38, h=10, center=true);
        for (i = [-16, 16], j = [-16, 16]) translate([22 + i, 1.5, 28 + j]) rotate([90, 0, 0]) cylinder(d=3.4, h=10, center=true);
        for (k = [-1, 1]) translate([22 + k*10, 18, -1]) cylinder(d=3.4, h=5);
    }
}

if (parte == "base") base();
else if (parte == "tapa") tapa();
else if (parte == "bandeja") bandeja();
else if (parte == "soporte_ventilador") soporte_ventilador();
else {
    base();
    color("SteelBlue", 0.5) translate([0, 0, H + piso + 30]) tapa();
    color("Silver") translate([Lx/2 - placa[0]/2, Wy/2 - placa[1]/2, piso + 15]) cube([placa[0], placa[1], 3]);
    color("Orange") translate([e + 1, e + 1, piso + z_bandeja]) bandeja();
}
