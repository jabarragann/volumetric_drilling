#include <iostream>
#include <vector>
#include "EdtReader/EdtReader.h"
#include <unordered_map>

// To display color
#include <algorithm>
#include <sstream>
#include <iterator>

#define number_of_edt 5

using std::string;
using std::vector;

class EdtContainer
{
public:
    float m_dist_object;
    string path;
    string name;
    Array3d<float> *edt_grid;
    vector<int> rgb;

    EdtContainer() {}
    EdtContainer(string p, string name, const vector<int> &rgb)
    {
        this->name = name;
        this->path = p;
        this->m_dist_object = 0.0;
        this->rgb = std::vector<int>(rgb.begin(), rgb.end());
    }

    void load_grid()
    {
        float *values_buffer;
        unsigned int res[3];
        edt_reader(this->path, &values_buffer, res);
        this->edt_grid = new Array3d<float>(values_buffer, res);

        // I will keep this error here to remember the importance of learning how to allocate memory in c++.
        //        Array3d<float> edtGrid(values_buffer, res);
        //        this->edt_grid = edtGrid;
    }
    void get_resolution(unsigned int *resolution)
    {
        *resolution = (this->edt_grid)->res[0];
        *(resolution + 1) = (this->edt_grid)->res[1];
        *(resolution + 2) = (this->edt_grid)->res[2];
    }
    void print_info()
    {
        // RGB vect to string
        std::ostringstream vts;
        std::copy(this->rgb.begin(), this->rgb.end(),
                  std::ostream_iterator<int>(vts, ", "));

        printf("name: %s || path: %s || color: %s \n", this->name.c_str(), this->path.c_str(), vts.str().c_str());
    }
};

std::string edt_paths[number_of_edt] = {"./edt_grids/IAC.edt",
                                        "./edt_grids/Sinus_+_Dura.edt",
                                        "./edt_grids/TMJ.edt",
                                        "./edt_grids/EAC.edt",
                                        "./edt_grids/ICA.edt"};

std::string edt_names[number_of_edt] = {"IAC",
                                        "Sinus_+_Dura",
                                        "TMJ",
                                        "EAC",
                                        "ICA"};
// Save colors
class EdtList
{
public:
    EdtContainer list[number_of_edt];
    std::unordered_map<string, vector<int>> color_map;

    EdtList()
    {
        color_map["IAC"] = vector<int>{244, 142, 52};
        color_map["Sinus_+_Dura"] = vector<int>{110, 184, 209};
        color_map["TMJ"] = vector<int>{100, 0, 0};
        color_map["EAC"] = vector<int>{255, 225, 214};
        color_map["ICA"] = vector<int>{216, 100, 79};

        printf("constructor\n");
        for (int i = 0; i < number_of_edt; i++)
        {
            printf("loading %d edt\n", i);
            EdtContainer cont(edt_paths[i], edt_names[i], color_map[edt_names[i]]);

            list[i] = cont;
        }
    }

    void load_all_grids()
    {
        for (int i = 0; i < number_of_edt; i++)
        {
            this->list[i].load_grid();
        }
    }
    void print_info()
    {
        printf("------------------------\n");
        printf("Printing edt information\n");
        printf("------------------------\n");
        for (int i = 0; i < number_of_edt; i++)
        {
            this->list[i].print_info();
        }
    }
};
