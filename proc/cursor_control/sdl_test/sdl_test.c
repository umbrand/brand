#include <sys/time.h>
#include <SDL2/SDL.h> 
#include <SDL2/SDL_image.h> 
#include <SDL2/SDL_timer.h> 
#include "SDL2/SDL_ttf.h"


int main() 
{ 

	struct timeval ct, lt;

	// retutns zero on success else non-zero 
	if (SDL_Init(SDL_INIT_EVERYTHING) != 0) { 
		printf("error initializing SDL: %s\n", SDL_GetError()); 
	} 
	TTF_Init();

	Uint32 window_flags = SDL_WINDOW_FULLSCREEN_DESKTOP;
	SDL_Window* win = SDL_CreateWindow("GAME", // creates a window 
									SDL_WINDOWPOS_CENTERED, 
									SDL_WINDOWPOS_CENTERED, 
									0, 0, window_flags); 

	int win_w, win_h;
	SDL_GetWindowSize(win, &win_w, &win_h);

	// triggers the program that controls 
	// your graphics hardware and sets flags 
	Uint32 render_flags = SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC; 

	// creates a renderer to render our images 
	SDL_Renderer* rend = SDL_CreateRenderer(win, -1, render_flags); 

	// creates a surface to load an image into the main memory 
	SDL_Surface* surface; 

	// please provide a path for your image 
	surface = IMG_Load("./yellow_circle.png"); 



	// loads image to our graphics hardware memory. 
	SDL_Texture* tex = SDL_CreateTextureFromSurface(rend, surface); 

	// clears main-memory 
	SDL_FreeSurface(surface); 

	// let us control our image position 
	// so that we can move it with our keyboard. 
	SDL_Rect dest; 

	// connects our texture with dest to control position 
	SDL_QueryTexture(tex, NULL, NULL, &dest.w, &dest.h); 

	// adjust height and width of our image box. 
	dest.w = 50; 
	dest.h = 50; 

	// sets initial x-position of object 
	dest.x = (win_w - dest.w) / 2; 

	// sets initial y-position of object 
	dest.y = (win_h - dest.h) / 2; 

	TTF_Font* Sans = TTF_OpenFont("Roboto-Regular.ttf", 50); //this opens a font style and sets a size
	SDL_Color White = {125, 125, 125};  // this is the color in rgb format, maxing out all would give you the color white, and it will be your text's color
	SDL_Surface* surfaceMessage = TTF_RenderText_Solid(Sans, "", White); // as TTF_RenderText_Solid could only be used on SDL_Surface then you have to create the surface first
	SDL_Texture* Message = SDL_CreateTextureFromSurface(rend, surfaceMessage); //now you can convert it into a texture

	//Get the texture w/h so we can center it in the screen
	int iW, iH;
	SDL_QueryTexture(Message, NULL, NULL, &iW, &iH);

	SDL_Rect Message_rect; //create a rect
	Message_rect.x = 0;  //controls the rect's x coordinate 
	Message_rect.y = 0; // controls the rect's y coordinte
	Message_rect.w = iW; // controls the width of the rect
	Message_rect.h = iH; // controls the height of the rect

	// controls annimation loop 
	int close = 0; 


	char refresh_rate_str[10];
	int irefresh = 0;

	gettimeofday(&lt,NULL);
	Uint32 lastTime = lt.tv_sec * 1000000 + lt.tv_usec;
	Uint32 currentTime;
	// annimation loop 
	while (!close) { 
		SDL_Event event; 

		// Events mangement 
		while (SDL_PollEvent(&event)) { 
			switch (event.type) { 

			case SDL_QUIT: 
				// handling of close button 
				close = 1; 
				break; 

			case SDL_MOUSEMOTION:
				dest.x = event.motion.x - (dest.w / 2);
				dest.y = event.motion.y - (dest.h / 2);
			}
		} 
		if (irefresh > 99) { // run every 100 frames
			gettimeofday(&ct,NULL);
			currentTime = ct.tv_sec * 1000000 + ct.tv_usec;;
			sprintf(refresh_rate_str, "%.2f", 100 * 1000000.0 / (currentTime - lastTime));
			lastTime = currentTime;
			irefresh = 0;
		}
		SDL_Surface* surfaceMessage = TTF_RenderText_Solid(Sans, refresh_rate_str, White); // as TTF_RenderText_Solid could only be used on SDL_Surface then you have to create the surface first
		SDL_Texture* Message = SDL_CreateTextureFromSurface(rend, surfaceMessage); //now you can convert it into a texture
		SDL_QueryTexture(Message, NULL, NULL, &Message_rect.w, &Message_rect.h);


		// clears the screen 
		SDL_RenderClear(rend); 
		SDL_RenderCopy(rend, tex, NULL, &dest); 
		SDL_RenderCopy(rend, Message, NULL, &Message_rect);

		// triggers the double buffers 
		// for multiple rendering 
		SDL_RenderPresent(rend); 
		irefresh++;
		// calculates to 60 fps 
		// SDL_Delay(1000 / 60); 
	} 

	// destroy texture 
	SDL_DestroyTexture(tex); 
	SDL_DestroyTexture(Message);

	// destroy renderer 
	SDL_DestroyRenderer(rend); 

	// destroy window 
	SDL_DestroyWindow(win); 


	
	return 0; 
} 
