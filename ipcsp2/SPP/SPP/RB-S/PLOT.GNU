set term post color
set title "Rb-S" font "Helvetica Bold, 48"
set xrange [0 to 10.5]
set ylabel "g(r)"
set xlabel "Distance r, A"
plo "Rb-S.av" u ($0/20+0.025):($1/($0/20+0.025)**2 * 1.59154943) w lp lw 2 pt 7 ps 4 lc "gray" t "384 ICSD structures"
rep "Rb-S.rdf" u 1:2 w l lw 4 lt 3 t "Gaussian smoothing"
rep "Rb-S.pot" u 1:(exp(-$2)) w l lw 2 lc "black" t "final exp(-SPP(r)) transform"
set term png truecolor enhanced lw 2 font "Helvetica, 32" size 1600,1200
set output "Rb-S.png"
rep
q
