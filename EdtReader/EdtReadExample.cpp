#include "EdtReader.h"
#include <iostream>
#include <stdexcept>

using namespace std;

int main()
{
    cout << "Edt reader example\n";

    string file_name = "./../grids/ear3_171.edt";
    char error_msg[100];
    sprintf(error_msg, "Reading %s", &file_name[0]);
    cout << error_msg << endl;

    // Read data in Array3D
    float *values_buffer;
    unsigned int res[3];
    edt_reader(file_name, &values_buffer, res);
    Array3d<float> edtGrid1(values_buffer, res);

    edtGrid1.print_resolution();
    for (int i = 0; i < 10; i++)
    {
        printf("Grid 1: %d %0.6f\n", i, edtGrid1(i, 0, i));
    }
    return 0;
}