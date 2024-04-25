#include "volume_slicer.h"

using namespace chai3d;

VolumeSlicer::VolumeSlicer(unsigned char const *const raw_data, array<string, 4> dim_names,
                           array<int, 4> volume_shape) : raw_data(raw_data), dim_names(dim_names), volume_shape(volume_shape)
{
    stride_array[0] = 1;
    stride_array[1] = volume_shape[0];
    stride_array[2] = volume_shape[0] * volume_shape[1];
    stride_array[3] = volume_shape[0] * volume_shape[1] * volume_shape[2];
};

unique_ptr<Slice2D> VolumeSlicer::create_2d_slice(std::array<int, 4> permutation_array, int slice_idx)
{
    //TODO: USE PERMUTATION ARRAY TO SLICE VOLUMES DIFFERENTLY.

    cImagePtr z_slice = cImage::create();
    z_slice->allocate(volume_shape[1], volume_shape[2], GL_RGBA, GL_UNSIGNED_BYTE);

    int z = 70;
    int W = volume_shape[1];
    int H = volume_shape[2];

    unsigned char r;
    unsigned char g;
    unsigned char b;
    unsigned char a;

    for (int y = 0; y < volume_shape[2]; y++)
    {
        for (int x = 0; x < volume_shape[1]; x++)
        {
            int pix_index = x * stride_array[1] + y * stride_array[2] + z * stride_array[3];
            cColorb colorz;
            r = raw_data[pix_index];
            g = raw_data[pix_index + 1];
            b = raw_data[pix_index + 2];
            a = raw_data[pix_index + 3];
            colorz.set(r, g, b, a);
            z_slice->setPixelColor(x, y, colorz);
        }
    }

    z_slice->saveToFile("slice_juan.png");

    return unique_ptr<Slice2D>();
}