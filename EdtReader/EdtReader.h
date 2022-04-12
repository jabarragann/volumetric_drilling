#include <iostream>

// Code taken from
// http://www.cplusplus.com/forum/general/36130/
template <typename T>
struct Array3d
{

public:
    T *data;
    unsigned res[3];

    Array3d()
    {
        data = NULL;
        res[0] = 0;
        res[1] = 0;
        res[2] = 0;
    }
    Array3d(unsigned *resolution)
    {
        this->res[0] = *resolution;
        this->res[1] = *(resolution + 1);
        this->res[2] = *(resolution + 2);
        this->data = new T[res[0] * res[1] * res[2]];
    }
    Array3d(T *data_pt, unsigned *resolution)
    {
        this->res[0] = *resolution;
        this->res[1] = *(resolution + 1);
        this->res[2] = *(resolution + 2);
        this->data = data_pt;
    }
    ~Array3d()
    {
        printf("Array 3d destructor called \n");
        delete[] data;
    }
    inline T &operator()(unsigned x, unsigned y, unsigned z)
    {
        // x+y*res[0]+z*res[0]*res[1]
        return data[x + y * res[0] + z * res[0] * res[1]];
    }
    inline const T &operator()(unsigned x, unsigned y, unsigned z) const
    {
        return data[x + y * res[0] + z * res[0] * res[1]];
    }
    inline unsigned size() const
    {
        return res[0], res[1], res[2];
    }
    void print_resolution()
    {
        printf("grid resolution: (%d,%d,%d)\n", res[0], res[1], res[2]);
    }
};

void edt_reader(std::string file_name, float **values_buffer, unsigned int *res);
