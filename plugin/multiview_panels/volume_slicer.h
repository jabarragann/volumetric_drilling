#include <iostream>
#include <array>
#include <string>
#include "chai3d.h"
#include <memory>

using std::array;
using std::cout;
using std::string;
using std::unique_ptr;

class Slice2D
{
    int slice_idx;
};

class VolumeSlicer
{

public:
    VolumeSlicer(unsigned char const *const raw_data, array<string, 4> dim_names, array<int, 4> volume_shape);
    unique_ptr<Slice2D> create_2d_slice(std::array<int, 4> permutation_array, int slice_idx);

private:
    array<string, 4> dim_names;
    array<int, 4> volume_shape;
    array<int, 4> stride_array;
    unsigned char const *const raw_data;
};