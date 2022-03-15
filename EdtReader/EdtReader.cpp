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
void edt_reader(string file_name)
{
    int Dim = 3;
    unsigned int res[3];
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
        printf("grid resolution: (%d,%d,%d)\n", res[0], res[1], res[2]);
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

        Array3d<float> edtGrid(res[0], res[1], res[2]);

        float *values_buffer;

        int total_values = res[0] * res[1] * res[2];
        values_buffer = (float *)malloc(sizeof(float) * total_values);
        // values = NewPointer<DataType>(_Resolution(res));
        // Read the grid values
        cout << "obtaining values" << endl;
        fread(values_buffer, sizeof(float), total_values, fp);
        fclose(fp);

        for (int i = 0; i < 10; i++)
        {
            printf("%d %0.6f\n", i, values_buffer[i]);
        }
    }
}

int main()
{
    cout << "Edt reader\n";

    string file_name = "./../grids/ear3_171.edt";

    char error_msg[100];
    sprintf(error_msg, "Reading %s", &file_name[0]);
    cout << error_msg << endl;

    edt_reader(file_name);

    return 0;
}