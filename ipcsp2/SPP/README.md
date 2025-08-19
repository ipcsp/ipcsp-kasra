# SPP
Statistical Proxy Potential data for the whole ICSD

The starting point for this data set was 200,809 cifs extracted from ICSD on 7 September 2021 using this script

https://github.com/lrcfmd/ICSDClient

All structures are from EXPERIMENTAL_INORGANIC subset of ICSD.

<li> 94,783 structures contained an atoms with occupancy less than one and were identified as disordered
<li>    247 .cif files were unreadable for the ASE and through an exception 
<li>105,779 .cif files were processed to calculate pair histograms using gen_pdf_partials_3.py

This produced 728,436 files with pair histograms for 3,388 unique atom pairs.

The number of structures that contained a given atom pair is given in ICSD_co-occurence_matrix.xlsx
For example, Helium was found in 12 out of 105,779 structures and only in one of them Hydrogen was also present.

Zipped folder SPP.zip contains 3,388 subfolders with the data for each identified atom pair.
For example, the Li-O folder contains six files:

<li>Li-O.ref - the list of 2,384 reference structures that were used to build the Li-O SPP (no filtering)
<li>Li-O.av  - the simple average of all histogram data for all reference structures before any smoothing is applied. These are the files needed to recompute the potentials using fit_potential.py.  
<li>Li-O.rdf - the average RDF obtained from the histogram data in Li-O.av by applying Gaussian smoothing with sigma=0.1 A and normalising the data by (4 pi r^2 dr).
<li>Li-O.pot - the final SPP produced form RDF in Li-O.rdf 
<li>plot.gnu - the gnuplot file that plots raw ICSD data as an RDF, Gaussian smoothed RDF data and SPP converted back to RDF.
<li>Li-O.png - the graph produced from gnu.gnu

If one wishes to re-fit the SPPs using a different smoothing protocol, for example, this can be done by altering fit_potential.py and running:

python fit_potential.py Li O
