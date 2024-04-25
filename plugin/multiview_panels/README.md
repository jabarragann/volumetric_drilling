# Strided indexing schemes

The following contains a list of resources that explain the algorithm used to extract 2D-slices out of a 1D array. This mechanism is similar to how numpy `ndarrays` are indexed.


## Key concepts:

* In a simple, flat layout, the fastest changing dimension has a stride of 1, and the stride of any higher dimension is equal to the number of elements in all the lower-dimension slices. 

## Resources:

Math for strided indexing schemes is provided in numpy documentation.

* <https://insight-journal.org/browse/publication/159>
* <https://numpy.org/doc/stable/reference/arrays.ndarray.html>
* <https://ipython-books.github.io/46-using-stride-tricks-with-numpy/>

Slicer3D documentation on coordinate systems (LPS is preferred of RAS).
* <https://slicer.readthedocs.io/en/latest/user_guide/coordinate_systems.html>

Slicer3D data probe.
* <https://www.slicer.org/wiki/Documentation/4.0/Modules/DataProbe>

Read only pointers
* https://stackoverflow.com/questions/13439580/pass-a-pointer-to-a-function-as-read-only-in-c