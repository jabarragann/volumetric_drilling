#include <iostream>
#include <stdexcept>
#include "EdtReader.h"

using namespace std;

bool read_data_type(FILE *fp, unsigned int dim, std::string name)
{
    char line[1024];
    int d;
    if (fscanf(fp, " %d %s ", &d, line) != 2)
        return false;
    cout << line << " " << d << endl;
    return d == dim && name == std::string(line);
}
// https://stackoverflow.com/questions/1398307/how-can-i-allocate-memory-and-return-it-via-a-pointer-parameter-to-the-calling

void edt_reader(string file_name, float **values_buffer, unsigned int *res)
{
    int Dim = 3;
    // unsigned int res[3];
    char error_msg[100];

    FILE *fp = fopen(file_name.c_str(), "rb");
    if (!fp)
        throw std::runtime_error("Error loading the file");
    else
    {
        // Read the magic number
        int dim;
        if (fscanf(fp, " G%d ", &dim) != 1)
        {
            sprintf(error_msg, "Failed to read magic number: %s", &file_name[0]);
            throw std::runtime_error(string(error_msg));
        }
        // Read the data type
        if (!read_data_type(fp, 1, "FLOAT"))
            throw std::runtime_error("Failed to read type");

        // Read the dimensions
        int r;
        for (int d = 0; d < Dim; d++)
        {
            if (fscanf(fp, " %d ", &r) != 1)
            {
                sprintf(error_msg, "Failed to read dimension[%d]", d);
                throw runtime_error(error_msg);
            }
            res[d] = r;
        }

        // Read the transformation
        float x;
        for (int j = 0; j < Dim + 1; j++)
        {
            for (int i = 0; i < Dim + 1; i++)
            {
                if (fscanf(fp, " %f", &x) != 1)
                {
                    sprintf(error_msg, "Failed to read xForm(%d,%d)", i, j);
                    throw runtime_error(error_msg);
                }
            }
        }
        // Read through the end of the line
        {
            char line[1024];
            if (!fgets(line, sizeof(line) / sizeof(char), fp))
                throw runtime_error("Could not read end of line");
        }
        // To access values in EDT
        // value(x,y,z) = array(x+y*res[0]+z*res[0]*res[1])

        int total_values = res[0] * res[1] * res[2];
        *values_buffer = (float *)malloc(sizeof(float) * total_values);
        // *values_buffer = new float[total_values];

        // Read the grid values
        fread(*values_buffer, sizeof(float), total_values, fp);
        fclose(fp);

        // This breaks the code.
        // TODO: Find out why
        //  Array3d<float> edtGrid(*values_buffer, res[0], res[1], res[2]);

        //  edtGrid.print_resolution();
        // for (int i = 0; i < 10; i++)
        // {
        //     printf("%d %0.6f\n", i, edtGrid(i, 0, 0));
        // }
    }
}
