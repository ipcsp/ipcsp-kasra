set term post color
set title "Si-Y" font "Helvetica Bold, 48"
set xrange [0 to 10.5]
set ylabel "g(r)"
set xlabel "Distance r, A"
plo "Si-Y.av" u ($0/20+0.025):($1/($0/20+0.025)**2 * 1.59154943) w lp lw 2 pt 7 ps 4 lc "gray" t "237 ICSD structures"
rep "Si-Y.rdf" u 1:2 w l lw 4 lt 3 t "Gaussian smoothing"
rep "Si-Y.pot" u 1:(exp(-$2)) w l lw 2 lc "black" t "final exp(-SPP(r)) transform"
set term png truecolor enhanced lw 2 font "Helvetica, 32" size 1600,1200
set output "Si-Y.png"
rep
q
