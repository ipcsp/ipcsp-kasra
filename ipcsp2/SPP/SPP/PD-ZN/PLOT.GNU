set term post color
set title "Pd-Zn" font "Helvetica Bold, 48"
set xrange [0 to 10.5]
set ylabel "g(r)"
set xlabel "Distance r, A"
plo "Pd-Zn.av" u ($0/20+0.025):($1/($0/20+0.025)**2 * 1.59154943) w lp lw 2 pt 7 ps 4 lc "gray" t "44 ICSD structures"
rep "Pd-Zn.rdf" u 1:2 w l lw 4 lt 3 t "Gaussian smoothing"
rep "Pd-Zn.pot" u 1:(exp(-$2)) w l lw 2 lc "black" t "final exp(-SPP(r)) transform"
set term png truecolor enhanced lw 2 font "Helvetica, 32" size 1600,1200
set output "Pd-Zn.png"
rep
q
