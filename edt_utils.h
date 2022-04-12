#include <iostream>
#include "EdtReader/EdtReader.h"

#define number_of_edt 3

std::string edt_paths[number_of_edt] = {"./edt_grids/IAC.edt",
                                        "./edt_grids/Sinus_+_Dura.edt",
                                        "./edt_grids/TMJ.edt"};

std::string edt_names[number_of_edt] = {"IAC",
                                        "Sinus_+_Dura",
                                        "TMJ"};

class EdtContainer
{
public:
    float m_dist_object;
    std::string path;
    std::string name;
    Array3d<float> *edt_grid;

    EdtContainer() {}
    EdtContainer(std::string p, std::string name)
    {
        this->name = name;
        this->path = p;
        this->m_dist_object = 0.0;
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

    void print_info()
    {
        printf("name: %s || path: %s \n", this->name.c_str(), this->path.c_str());
    }
};

class EdtList
{
public:
    EdtContainer list[number_of_edt];

    EdtList()
    {

        printf("constructor\n");
        for (int i = 0; i < number_of_edt; i++)
        {
            printf("loading %d edt\n", i);
            EdtContainer cont(edt_paths[i], edt_names[i]);
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
