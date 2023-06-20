# MONDPMesh
Python N-body code made for MOND simulations.

This code uses an altered particle mesh method to solve the Poisson equation of the AQUAL version of MOND. It was made for my Bachelor's thesis. The thesis can be found at https://repository.tudelft.nl/.

The example file contains the complete code together with an example simulation of a two body system. This file can be immediately run when the required libraries are installed, and will plot the trajectories of the bodies with the total energy. Both of these are plotted together with exact formula for these quantities. 

The Clean file contains the complete code without anything else. You can create a particlelist object and run simulations yourself. This file also includes comments on what the code does.

Please message me if you find any errors or bugs.



Required libraries:
Numpy, math, itertools, these are all included in base Python
Pyfftw, which needs the C FFTW library. Its documentation can be found in https://pyfftw.readthedocs.io/en/latest/. 


