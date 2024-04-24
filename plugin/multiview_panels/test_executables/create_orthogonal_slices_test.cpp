
#include <iostream>
#include <afFramework.h>

using namespace std;
using namespace ambf;

// image_ptr->getType() GL_UNSIGNED_BYTE 0x1401 --> 5121
// image_ptr->getFormat() GL_RGBA 0x1908 --> 6408

void print_volume_information(cMultiImagePtr volume_slices_ptr)
{
    cout << "image count " << volume_slices_ptr->getImageCount() << endl;
    cout << "get current idx " << volume_slices_ptr->getCurrentIndex() << endl;
    cout << "(width, height) = (" << volume_slices_ptr->getWidth() << ", " << volume_slices_ptr->getHeight() << ")" << endl;
    cout << "get fmt " << volume_slices_ptr->getFormat() << endl;
    cout << "get type " << volume_slices_ptr->getType() << endl;
    cout << "get bits per pixel " << volume_slices_ptr->getBitsPerPixel() << endl;
    cout << "\n\n\n\n"
         << endl;
}

int main()
{
    std::cout << "test volume slicing" << std::endl;

    //--------------------------------------------------------------------------
    // CREATE VOXEL DATA
    //--------------------------------------------------------------------------

    // create multi image data structure
    cMultiImagePtr mult_img = cMultiImage::create();
    string base_path = "../resources/volumes/ear3_171/plane00";
    string extension = "png";
    int images_loaded = mult_img->loadFromFiles(base_path, extension);

    cout << "Loaded " << images_loaded << " images" << endl;

    print_volume_information(mult_img);

    // Get raw data
    unsigned char *raw_data = mult_img->getData();

    // create a new slice
    cImagePtr z_slice = cImage::create();
    z_slice->allocate(mult_img->getWidth(), mult_img->getHeight(), mult_img->getFormat(), mult_img->getType());

    cImagePtr x_slice = cImage::create();
    x_slice->allocate(mult_img->getWidth(), mult_img->getHeight(), mult_img->getFormat(), mult_img->getType());
    /* x_slice->allocate(mult_img->getWidth(), 169, mult_img->getFormat(), mult_img->getType()); */

    int z = 50;
    int W = mult_img->getWidth();
    int H = mult_img->getHeight();
    unsigned char r;
    unsigned char g;
    unsigned char b;
    unsigned char a;

    for (int y = 0; y < 169; y++)
    {
        for (int x = 0; x < mult_img->getWidth(); x++)
        {
            cColorb colorz;
            r = raw_data[z * W * H * 4 + y * 4 + x * W * 4];
            g = raw_data[z * W * H * 4 + y * 4 + x * W * 4 + 1];
            b = raw_data[z * W * H * 4 + y * 4 + x * W * 4 + 2];
            a = raw_data[z * W * H * 4 + y * 4 + x * W * 4 + 3];
            colorz.set(r, g, b, a);
            z_slice->setPixelColor(x, y, colorz);

            cColorb colorx;
            r = raw_data[z * W * 4 + y * W * H * 4 + x * 4];
            g = raw_data[z * W * 4 + y * W * H * 4 + x * 4 + 1];
            b = raw_data[z * W * 4 + y * W * H * 4 + x * 4 + 2];
            a = raw_data[z * W * 4 + y * W * H * 4 + x * 4 + 3];
            colorx.set(r, g, b, a);
            x_slice->setPixelColor(x, y, colorx);
        }
    }

    z_slice->saveToFile("z_slice.png");
    x_slice->saveToFile("x_slice.png");

    cout << "Finish slicing test" << endl;
}
