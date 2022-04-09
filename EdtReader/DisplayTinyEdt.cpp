#include "EdtReader.h"
#include <iostream>
#include <stdexcept>

using namespace std;

int main()
{
    cout << "Display tiny edt\n";

    string file_name = "./../grids/cube40_32.edt";

    // Read file
    char error_msg[100];
    sprintf(error_msg, "Reading %s", &file_name[0]);
    cout << error_msg << endl;

    // Read data in Array3D
    float *values_buffer;
    unsigned int res[3];
    edt_reader(file_name, &values_buffer, res);
    Array3d<float> edtGrid1(values_buffer, res);
    edtGrid1.print_resolution();

    // for (int i = 0; i < 10; i++)
    // {
    //     printf("Grid 1: %d %0.6f\n", i, edtGrid1(i, 0, i));
    // }

    // Test data accessing methods
    printf("Test data accessing methods.\n");
    printf("print c for edt values equal to 4.0 and o otherwise\n");
    printf("-----------------------\n");
    float val;
    printf("   ");
    for (int x = 0; x < res[0]; x++)
        printf("%3d", x);
    printf("\n");
    for (int y = 0; y < res[1]; y++)
    {
        printf("%3d", y);
        for (int x = 0; x < res[0]; x++)
        {
            val = edtGrid1(x, y, 0);
            char c;
            c = (val == 4.0) ? 'c' : 'o';
            printf("  %c", c);
        }
        printf("\n");
    }
    printf("-----------------------\n");
    return 0;
}