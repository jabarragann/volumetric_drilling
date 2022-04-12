#include "../edt_utils.h"

int main()
{
    printf("Test edt loaders/utils\n");

    EdtList edt_list;
    edt_list.print_info();
    edt_list.load_all_grids();

    return 0;
}
