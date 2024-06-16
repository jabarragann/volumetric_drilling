#include <iostream>
#include <array>
#include <string>
#include "chai3d.h"
#include <memory>

using std::vector;
using std::array;
using std::cout;
using std::endl;
using std::string;
using std::unique_ptr;

const int NUM_OF_DIM = 4;
typedef std::map<string, std::array<int, NUM_OF_DIM>> MapOfArrays;
typedef std::map<string, std::array<string, NUM_OF_DIM>> MapOfStringArrays;

class Slice2D
{
    int slice_idx;
};

class VolumeSlicer
{

public:
    VolumeSlicer(unsigned char const *const raw_data, array<string, 4> dim_names, array<int, 4> volume_shape);
    unique_ptr<Slice2D> create_2d_slice(string slice_name, array<int, 4> permutation_array, int slice_idx);
    void permute_array(const array<int, NUM_OF_DIM> &arr, const vector<int> &indexes, array<int, NUM_OF_DIM> &out_arr);
    void permute_array(const array<string, NUM_OF_DIM> &arr, const vector<int> &indexes, array<string, NUM_OF_DIM> &out_arr);

    void fill_slice_maps(string slice_name, const vector<int> &permutation_indexes);
    void print_slices_information();

private:
    MapOfArrays strides_map;
    MapOfArrays limits_map;
    MapOfStringArrays names_map;
    MapOfStringArrays stride_expressions_map;

    array<string, 4> dim_names;
    array<string, 4> stride_expressions;
    array<int, 4> volume_shape;
    array<int, 4> stride_array;
    unsigned char const *const raw_data;
};