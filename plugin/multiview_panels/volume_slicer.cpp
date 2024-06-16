#include "volume_slicer.h"
#include <sstream>

using namespace chai3d;

/**
 * Create strides arrays for VolumeSlicer.
 *
 * Each slice can be generated by permutating the stride array of the volume. The array containing the shape of the volume
 * also need to be permutated as not all dimensions might have the same size
 *
 */
VolumeSlicer::VolumeSlicer(unsigned char const *const raw_data, array<string, 4> dim_names,
                           array<int, 4> volume_shape) : raw_data(raw_data), dim_names(dim_names), volume_shape(volume_shape)
{
    stride_array[0] = 1;
    stride_array[1] = volume_shape[0];
    stride_array[2] = volume_shape[0] * volume_shape[1];
    stride_array[3] = volume_shape[0] * volume_shape[1] * volume_shape[2];

    stride_expressions[0] = dim_names[0];
    stride_expressions[1] = dim_names[0] + "*" + dim_names[1];
    stride_expressions[2] = dim_names[0] + "*" + dim_names[1] + "*" + dim_names[2];
    stride_expressions[3] = dim_names[0] + "*" + dim_names[1] + "*" + dim_names[2] + "*" + dim_names[3];

    fill_slice_maps("xy", {0, 1, 2, 3});
    fill_slice_maps("yz", {0, 2, 3, 1});
    fill_slice_maps("xz", {0, 1, 3, 2});
};

void VolumeSlicer::fill_slice_maps(std::string slice_name, const std::vector<int> &permutation_indexes)
{
    array<int, 4> slice_strides;
    array<int, 4> slice_limits;
    array<string, 4> slice_names;
    array<string, 4> slice_expressions;

    permute_array(stride_array, permutation_indexes, slice_strides);
    strides_map[slice_name] = slice_strides;
    permute_array(volume_shape, permutation_indexes, slice_limits);
    limits_map[slice_name] = slice_limits;
    permute_array(dim_names, permutation_indexes, slice_names);
    names_map[slice_name] = slice_names;
    permute_array(stride_expressions, permutation_indexes, slice_expressions);
    stride_expressions_map[slice_name] = slice_expressions;
}

void VolumeSlicer::print_slices_information()
{
    for (auto const &entry : strides_map)
    {
        cout << "Slice: " << entry.first << endl;
        cout << "Strides: ";
        for (auto const &stride : entry.second)
        {
            cout << stride << " ";
        }
        cout << endl;

        cout << "Strides expressions: ";
        for (auto const &stride : stride_expressions_map[entry.first])
        {
            cout << stride << " ";
        }
        cout << endl;

        cout << "Limits: ";
        for (auto const &limit : limits_map[entry.first])
        {
            cout << limit << " ";
        }
        cout << endl;

        cout << "Names: ";
        for (auto const &name : names_map[entry.first])
        {
            cout << name << " ";
        }
        cout << endl;

        cout << "Index calculation: [";
        int i = 0;
        for (auto const &exp : stride_expressions_map[entry.first])
        {
            cout << exp << "*" << "i" << i << " + ";
            i++;
        }
        cout << "]" << endl;

        cout << endl;
    }
}

unique_ptr<Slice2D> VolumeSlicer::create_2d_slice(string slice_name, std::array<int, 4> permutation_array, int slice_idx)
{
    if (strides_map.find(slice_name) == strides_map.end())
    {
        throw std::invalid_argument("Slice name not found");
    }

    array<int, NUM_OF_DIM> slice_strides = strides_map[slice_name];
    array<int, NUM_OF_DIM> slice_limits = limits_map[slice_name];

    cImagePtr z_slice = cImage::create();
    z_slice->allocate(slice_limits[1], slice_limits[2], GL_RGBA, GL_UNSIGNED_BYTE);

    int z = 70;
    int W = slice_limits[1];
    int H = slice_limits[2];

    unsigned char r;
    unsigned char g;
    unsigned char b;
    unsigned char a;

    for (int y = 0; y < slice_limits[2]; y++)
    {
        for (int x = 0; x < slice_limits[1]; x++)
        {
            int pix_index = x * slice_strides[1] + y * slice_strides[2] + z * slice_strides[3];
            cColorb colorz;
            r = raw_data[pix_index];
            g = raw_data[pix_index + 1];
            b = raw_data[pix_index + 2];
            a = raw_data[pix_index + 3];
            colorz.set(r, g, b, a);
            z_slice->setPixelColor(x, y, colorz);
        }
    }

    std::stringstream ss;
    ss << "slice_" << slice_name << "_" << slice_idx << ".png";
    string output_filename = ss.str();
    z_slice->saveToFile(output_filename);

    return unique_ptr<Slice2D>();
}

void VolumeSlicer::permute_array(const std::array<int, NUM_OF_DIM> &arr, const std::vector<int> &indexes, std::array<int, NUM_OF_DIM> &out_arr)
{
    if (indexes.size() != NUM_OF_DIM)
    {
        throw std::invalid_argument("Index list size must match the array size");
    }

    for (int i = 0; i < NUM_OF_DIM; ++i)
    {
        out_arr[i] = arr[indexes[i]];
    }
}

void VolumeSlicer::permute_array(const std::array<string, NUM_OF_DIM> &arr, const std::vector<int> &indexes, std::array<string, NUM_OF_DIM> &out_arr)
{
    if (indexes.size() != NUM_OF_DIM)
    {
        throw std::invalid_argument("Index list size must match the array size");
    }

    for (int i = 0; i < NUM_OF_DIM; ++i)
    {
        out_arr[i] = arr[indexes[i]];
    }
}
