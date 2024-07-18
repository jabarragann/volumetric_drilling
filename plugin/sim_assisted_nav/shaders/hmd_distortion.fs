#version 120

// in vec2 gl_TexCoord;

//per eye texture to warp for lens distortion
uniform sampler2D warpTexture1;
uniform sampler2D warpTexture2;

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
        gl_FragColor = texture2D(warpTexture2, output_loc); 
    }
    else
    {
        gl_FragColor = texture2D(warpTexture1, output_loc); 
    }

   
}
