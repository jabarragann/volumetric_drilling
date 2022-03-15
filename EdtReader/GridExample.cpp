#include <iostream>
#include "EdtReader.h"

using namespace std;

int main()
{
    cout << "Grid example!" << endl;

    Array3d<float> grid(3, 3, 3);
    float counter = 0.0;
    for (int i = 0; i < 3; i++)
    {
        for (int j = 0; j < 3; j++)
        {
            for (int k = 0; k < 3; k++)
            {
                grid(k, j, i) = counter;
                counter++;
            }
        }
    }

    float *ptr = grid.data;
    for (int i = 0; i < 9; i++)
    {
        printf("%d %.6f\n", i, *ptr);
        ptr++;
    }
}