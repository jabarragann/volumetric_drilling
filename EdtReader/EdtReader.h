#include <iostream>

// Code taken from
// http://www.cplusplus.com/forum/general/36130/
template <typename T>
struct Array3d
{

public:
    T *data;
    unsigned width, height, length;

    Array3d()
    {
        data = NULL;
        width = 0;  // res[0]
        height = 0; // res[1]
        length = 0; // res[2]
    }
    Array3d(const Array3d<T> &other)
    {
        unsigned x, size = other.width * other.height * other.length;
        data = new T[size];
        width = other.width;
        height = other.height;
        length = other.length;
        for (x = 0; x < size; ++x)
        {
            data[x] = other.data[x];
        }
    }
    Array3d(unsigned w, unsigned h, unsigned l)
    {
        width = w;
        height = h;
        length = l;
        data = new T[width * length * height];
    }
    Array3d(T *data_pt, unsigned w, unsigned h, unsigned l)
    {
        width = w;
        height = h;
        length = l;
        data = data_pt;
    }
    ~Array3d()
    {
        delete[] data;
    }
    inline T &operator()(unsigned x, unsigned y, unsigned z)
    {
        // x+y*res[0]+z*res[0]*res[1]
        return data[x + y * width + z * width * height];
    }
    inline const T &operator()(unsigned x, unsigned y, unsigned z) const
    {
        return data[x + y * width + z * width * height];
    }
    inline unsigned size() const
    {
        return width * height * length;
    }
    void print_resolution()
    {
        printf("grid resolution: (%d,%d,%d)\n", width, height, length);
    }
};

void edt_reader(std::string file_name, float **values_buffer, unsigned int *res);