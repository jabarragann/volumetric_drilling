#include <iostream>
#include "volume_slicer.h"
#include "afFramework.h"

using namespace std;
using namespace ambf;

void print_volume_information(cMultiImagePtr volume_slices_ptr)
{
    cout << "Volume report: " << endl;
    cout << "image count " << volume_slices_ptr->getImageCount() << endl;
    cout << "get current idx " << volume_slices_ptr->getCurrentIndex() << endl;
    cout << "(width, height) = (" << volume_slices_ptr->getWidth() << ", " << volume_slices_ptr->getHeight() << ")" << endl;
    cout << "get fmt " << volume_slices_ptr->getFormat() << endl;
    cout << "get type " << volume_slices_ptr->getType() << endl;
    cout << "get bits per pixel " << volume_slices_ptr->getBitsPerPixel() << endl;
    cout << "\n"
         << endl;
}
void generate_stride_array(cMultiImagePtr volume, array<int, 4> &out_array)
{
    out_array[0] = volume->getBitsPerPixel() / 8;
    out_array[1] = volume->getWidth();
    out_array[2] = volume->getHeight();
    out_array[3] = volume->getImageCount();
}

int main()
{
    std::cout << "test volume slicing" << std::endl;

    // Load volume
    cMultiImagePtr mult_img = cMultiImage::create();
    string base_path = "../resources/volumes/RT143_256/plane00";
    string extension = "png";
    int images_loaded = mult_img->loadFromFiles(base_path, extension);

    cout << "Loaded " << images_loaded << " images" << endl;
    print_volume_information(mult_img);

    // Get raw data
    unsigned char const *const raw_data = mult_img->getData();

    array<int, 4> volume_shape;
    array<string, 4> dim_names = {"B", "W", "H", "D"};
    generate_stride_array(mult_img, volume_shape);
    VolumeSlicer volume_slicer(raw_data, dim_names, volume_shape);

    volume_slicer.create_2d_slice({0, 1, 2, 3}, 70);
}