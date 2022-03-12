// Code taken from
// http://www.cplusplus.com/forum/general/36130/

template <typename T>
struct Array3d
{
protected:
    T *data;
    unsigned width, height, length;

public:
    Array3d()
    {
        data = NULL;
        width = 0;
        height = 0;
        length = 0;
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
    ~Array3d()
    {
        delete[] data;
    }
    inline T &operator()(unsigned x, unsigned y, unsigned z)
    {
        return data[z * width * height + y * width + x];
    }
    inline const T &operator()(unsigned x, unsigned y, unsigned z) const
    {
        return data[z * width * height + y * width + x];
    }
    inline unsigned size() const
    {
        return width * height * length;
    }
};