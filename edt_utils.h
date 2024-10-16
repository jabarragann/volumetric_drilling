#include <iostream>
#include <vector>
#include "EdtReader/EdtReader.h"
#include <unordered_map>

// To display color
#include <algorithm>
#include <sstream>
#include <iterator>

#define number_of_edt 15

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
    float force_thres;
    float audio_thres;

    EdtContainer() {}
    EdtContainer(string p, string name, const vector<int> &rgb, const float force_thres=1.0, const float audio_thres=1.0)
    {
        this->name = name;
        this->path = p;
        this->m_dist_object = 0.0;
        this->rgb = std::vector<int>(rgb.begin(), rgb.end());
        this->force_thres = force_thres;
        this->audio_thres = audio_thres;
    }

    void load_grid(string edt_root)
    {
        string complete_path = edt_root+this->path;

        float *values_buffer;
        unsigned int res[3];
        edt_reader(complete_path, &values_buffer, res);
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
    void setThreshold(float force_thres, float audio_thres)
    {
        this->force_thres = force_thres;
        this->audio_thres = audio_thres;
    }
};

std::string edt_paths[number_of_edt] = {"IAC.edt",
                                        "Sinus_+_Dura.edt",
                                        "TMJ.edt",
                                        "ICA.edt",
                                        "Malleus.edt",
                                        "Incus.edt",
                                        "Stapes.edt",
                                        "Bony_Labyrinth.edt",
                                        "Superior_Vestibular_Nerve.edt",
                                        "Inferior_Vestibular_Nerve.edt",
                                        "Cochlear_Nerve.edt",
                                        "Facial_Nerve.edt",
                                        "Chorda_Tympani.edt",
                                        "Vestibular_Aqueduct.edt",
                                        "EAC.edt"};
                                        // "./edt_grids/Bone.edt"};

std::string edt_names[number_of_edt] = {"IAC",
                                        "Dura",
                                        "TMJ",
                                        "ICA",
                                        "Malleus",
                                        "Incus",
                                        "Stapes",
                                        "Bony_Labyrinth",
                                        "Superior_Vestibular_Nerve",
                                        "Inferior_Vestibular_Nerve",
                                        "Cochlear_Nerve",
                                        "Facial_Nerve",
                                        "Chorda_Tympani",
                                        "Vestibular_Aqueduct",
                                        "EAC"};
                                        // "Bone"};


// Save colors
class EdtList
{
public:
    EdtContainer list[number_of_edt];
    std::unordered_map<string, vector<int>> color_map;
    std::unordered_map<string, vector<double>> thres_map;
    int size = number_of_edt;

    EdtList()
    {
        color_map["IAC"] = vector<int>{244, 142, 52};
        color_map["Dura"] = vector<int>{110, 184, 209};
        color_map["TMJ"] = vector<int>{100, 0, 0};
        color_map["EAC"] = vector<int>{255, 225, 214};
        color_map["ICA"] = vector<int>{216, 100, 79};
        color_map["Malleus"] = vector<int>{233, 0, 255};
        color_map["Incus"] = vector<int>{0, 255, 149};
        color_map["Stapes"] = vector<int>{63, 0, 255};
        color_map["Bony_Labyrinth"] = vector<int>{91, 123, 91};
        color_map["Superior_Vestibular_Nerve"] = vector<int>{255, 191, 135};
        color_map["Inferior_Vestibular_Nerve"] = vector<int>{121, 70, 24};
        color_map["Cochlear_Nerve"] = vector<int>{219, 244, 52};
        color_map["Facial_Nerve"] = vector<int>{244, 214, 49};
        color_map["Chorda_Tympani"] = vector<int>{151, 131, 29};
        color_map["Vestibular_Aqueduct"] = vector<int>{91, 98, 123};
        // color_map["Bone"] = vector<int>{255, 249, 219};//16

        thres_map["IAC"] = vector<double>{1.0,1.0};
        thres_map["Dura"] = vector<double>{0.5, 1.0};
        thres_map["TMJ"] = vector<double>{1.0,1.0};
        thres_map["EAC"] = vector<double>{0.5,1.0};
        thres_map["ICA"] = vector<double>{1.0,1.0};
        thres_map["Malleus"] = vector<double>{1.0,1.0};
        thres_map["Incus"] = vector<double>{0.5,1.0};
        thres_map["Stapes"] = vector<double>{0.5,1.0};
        thres_map["Bony_Labyrinth"] = vector<double>{0.5,1.0};
        thres_map["Superior_Vestibular_Nerve"] = vector<double>{1.0,1.0};
        thres_map["Inferior_Vestibular_Nerve"] = vector<double>{1.0,1.0};
        thres_map["Cochlear_Nerve"] = vector<double>{1.0,1.0};
        thres_map["Facial_Nerve"] = vector<double>{0.25,0.5};
        thres_map["Chorda_Tympani"] = vector<double>{0.25,0.5};
        thres_map["Vestibular_Aqueduct"] = vector<double>{1.0,1.0};


        

        printf("constructor\n");
        for (int i = 0; i < number_of_edt; i++)
        {
            printf("loading %d edt\n", i);
            EdtContainer cont(edt_paths[i], edt_names[i], color_map[edt_names[i]], thres_map[edt_names[i]][0], thres_map[edt_names[i]][1]);

            list[i] = cont;
        }
    }

    void load_all_grids(string edt_root)
    {
        for (int i = 0; i < number_of_edt; i++)
        {
            this->list[i].load_grid(edt_root);
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
