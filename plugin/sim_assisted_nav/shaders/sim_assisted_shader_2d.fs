// 2D mode: a single full-width eye image with one floating navigation window.
// Companion to sim_assisted_shader_3d.fs (3D / picture-over-picture mode).
// Shares the same uniforms so the ros_interface parameters (disparity, offset,
// show/hide) behave identically in both modes.
//
// IMPORTANT parameters:
// * small_window_disparity: shifts the window's left edge, same as in 3D mode
//   (see small_window_x_pos below -- its resting position isn't 0).
// * rect_size: size of the small window.

#version 120

// UNIFORMS
// Single eye image, stretched across the full window (2D mode).
uniform sampler2D rosImageTexture;
// Texture containing the simulation assisted navigation view.
uniform sampler2D frameBufferTexture;
// distance of small window from the left edge of the screen. Value between [0.0, 0.2]
uniform float small_window_disparity = 0.1;
// Toggles the floating navigation window. When false, only rosImageTexture is displayed.
uniform bool show_small_window = true;
// Offset of the small window from its default position.
uniform float small_window_horizontal_offset = 0.00;
uniform float small_window_vertical_offset = 0.00;

// Goovis pro window size. Kept identical to sim_assisted_shader_3d.fs so the
// nav window keeps the same visual size/shape in both modes.
int window_width = 2560; //
int window_height = 720; // goovis screen width is half in 3D mode (1440/2);

// CONFIG PARAMETERS
float small_window_y_pos = 0.60;
float small_window_height = 0.40;

// Adjust the small window's width to ensure it is always square
float aspect_ratio = float(window_width) / float(window_height);
float small_window_width = small_window_height / aspect_ratio;

vec2 rect_size = vec2(small_window_width, small_window_height);

// Match the 3D shader's left-eye window position. There, the window's left
// edge sits at left_x_pos_3d within the [0, 0.5] half-width the left eye is
// drawn into; scaling that by 2 places it at the same relative spot within
// this shader's full [0, 1] width (e.g. 0.3 of 0.5 in 3D -> 0.6 of 1.0 here).
// Not an exact visual match (rect_size below isn't rescaled the same way),
// but close enough to feel consistent between modes.
float left_x_pos_3d = 0.5 - rect_size.x - small_window_disparity + small_window_horizontal_offset;
float small_window_x_pos = 2.0 * left_x_pos_3d;
vec2 small_window_pos = vec2(small_window_x_pos, small_window_y_pos + small_window_vertical_offset);

float remap(float t, float a, float b, float c, float d)
{
    return c + (t-a)/(b-a) * (d-c);
}

// Remap function
// https://math.stackexchange.com/questions/914823/shift-numbers-into-a-different-range
vec2 remap_little_window(vec2 output_loc, vec2 rectMin, vec2 rectMax)
{
    float x2 = remap(output_loc.x, rectMin.x, rectMax.x, 0.0, 1.0);
    float y2 = remap(output_loc.y, rectMin.y, rectMax.y, 0.0, 1.0);
    vec2 remapped = vec2(x2, y2);
    return remapped;
}

void main()
{
    // output_loc is the fragment location on screen from [0,1]x[0,1]
    vec2 output_loc = gl_TexCoord[0].xy;

    // Rectangle boundaries in normalized device coordinates
    vec2 rectMin = small_window_pos;
    vec2 rectMax = small_window_pos + rect_size;

    if (show_small_window &&
        output_loc.x >= rectMin.x && output_loc.x <= rectMax.x &&
        output_loc.y >= rectMin.y && output_loc.y <= rectMax.y)
    {
        vec2 output_loc2 = remap_little_window(output_loc, rectMin, rectMax);
        gl_FragColor = mix(texture2D(frameBufferTexture, output_loc2), texture2D(rosImageTexture, output_loc), 0.1);
    }
    else
    {
        gl_FragColor = texture2D(rosImageTexture, output_loc);
    }
}
