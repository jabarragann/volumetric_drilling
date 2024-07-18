#version 120

// in vec2 gl_TexCoord;

//per eye texture to warp for lens distortion
uniform sampler2D rosImageTexture;
uniform sampler2D frameBufferTexture;

//Position of lens center in m (usually eye_w/2, eye_h/2)
uniform vec2 LensCenterLeft;
//Position of lens center in m (usually eye_w/2, eye_h/2)
uniform vec2 LensCenterRight;
//Scale from texture co-ords to m (usually eye_w, eye_h)
uniform vec2 ViewportScale;
//Distortion overall scale in m (usually ~eye_w/2)
uniform float WarpScale;
//Distoriton coefficients (PanoTools model) [a,b,c,d]
uniform vec4 HmdWarpParam;

//chromatic distortion post scaling
uniform vec3 aberr;
float offset;

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

    if (output_loc[0] <= 0.5)
    {
        offset = 0.0;
    }
    else
    {
        offset = 0.5;
    }

    // Rectangle boundaries in normalized device coordinates
    vec2 u_rectPos = vec2(0.1, 0.8);
    vec2 u_rectSize = vec2(0.15, 0.15);
    vec2 rectMin = u_rectPos;
    vec2 rectMax = u_rectPos + u_rectSize;
    rectMin.x += offset;
    rectMax.x += offset;

    if (output_loc.x >= rectMin.x && output_loc.x <= rectMax.x &&
        output_loc.y >= rectMin.y && output_loc.y <= rectMax.y)
    {
        // gl_FragColor = vec4(0.0, 1.0, 0.0, 1.0); // Green color
        vec2 output_loc2 = remap_little_window(output_loc, rectMin, rectMax);
        gl_FragColor = texture2D(frameBufferTexture, output_loc2); 
    }
    else
    {
        gl_FragColor = texture2D(rosImageTexture, output_loc); 
    }

   
}
