#include <iostream>
#include "EdtReader.h"

using namespace std;

int main()
{
    cout << "Grid structures tests!" << endl;
    unsigned int res[3] = {5, 3, 2};
    Array3d<float> grid(res);
    float counter = 0.0;
    for (int i = 0; i < res[2]; i++)
    {
        for (int j = 0; j < res[1]; j++)
        {
            for (int k = 0; k < res[0]; k++)
            {
                grid(k, j, i) = counter;
                counter++;
            }
        }
    }

    float *ptr = grid.data;
    for (int i = 0; i < 6; i++)
    {
        printf("%d %.6f\n", i, *ptr);
        ptr++;
    }

    // Test data accessing methods
    printf("Test data accessing methods.\n");
    printf("-----------------------\n");
    for (int z = 0; z < res[2]; z++)
    {
        for (int y = 0; y < res[1]; y++)
        {
            for (int x = 0; x < res[0]; x++)
            {
                printf("%4.1f ", grid(x, y, z));
            }
            printf("\n");
        }
        printf("-----------------------\n");
    }
}