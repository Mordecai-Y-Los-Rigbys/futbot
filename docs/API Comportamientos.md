# API DE CÓDIGO DE COMPORTAMIENTOS

Esta API corresponde a la interfaz de comunicación de código de comportamientos entre el usuario y el sistema.

**SE CONSIDERA INVÁLIDO CUALQUIER CÓDIGO QUE POSEA:**

* **IMPORTS DE ALGÚN TIPO**  
* **USO DE CUALQUIER ESTRUCTURA (QUE NO SEA UNA FUNCIÓN PRIMITIVA PROVISTA POR EL SISTEMA) EN PYTHON DE LA FORMA nombre()** (Incluye, en particular, definiciones de funciones, llamadas a funciones no primitivas del sistema y definición y construcción de clases y objetos)  
* **USO DE ESTRUCTURAS DE REPETICIÓN DE CÓDIGO:**  
  * while  
  * for  
  * iterables  
* **MÁS DE 250 LÍNEAS DE CÓDIGO**  
* **ERRORES DE SINTAXIS DEL LENGUAJE PYTHON**

Se permite el uso de IFs y el uso de asignaciones y lecturas de variables. 

El código asociado a un jugador se ejecutará por completo en un solo tick, excepto cuando:

* El código consume demasiados recursos y tarda demasiado tiempo, interrumpiéndose su ejecución cuando pase cierto umbral de consumo de recursos.  
* Un error es alzado por una primitiva o por el propio interpreter de Python, en cuyo caso se interrumpe su ejecución cuando el error ocurre.

## Constantes primitivas provistas:

* `largo\_cancha : int` \= aun no definida 
* `ancho\_cancha : int` \= aun no definida  
* `mi\_arco` \= (0, ancho\_cancha / 2\)  
* `arco\_rival` \= (largo\_cancha, ancho\_cancha / 2\)  
* `esq\_sup\_izq` \= (0, 0\)  
* `esq\_sup\_der` \= (0, largo\_cancha)  
* `esq\_inf\_izq` \= (ancho\_cancha, 0\)  
* `esq\_inf\_der` \= (ancho\_cancha, largo\_cancha)  
* `centro\_cancha` \= (alto\_cancha / 2, ancho\_cancha / 2\)  
* `largo\_arco : int` \= aun no definida

## **Funciones primitivas:**

### `moverse_direccion(dir_x : float, dir_y : float):`   
  * Argumentos:   
    - `dir_x : float`  
      La dirección x en la que se va a mover el jugador. Si es inferior a \-1, se toma como \-1 y si es mayor a 1, se toma como 1\.   
	
    - `dir_y : float`  
      La dirección y en la que se va a mover el jugador. Si es inferior a \-1, se toma como \-1 y si es mayor a 1, se toma como 1\.
    
    El jugador se mueve en la dirección (dir\_x, dir\_y). Si la suma |(dir\_x)² \+ (dir\_y)²| es distinto de 1, los valores se normalizan, es decir, se reducen proporcionalmente hasta que |(dir\_x)² \+ (dir\_y)²| \= 1\.

	`Devuelve: Null`

### `ir_a(coord\_x : int, coord\_y : int):`  
  - Argumentos:   
	  - `coord_x : int`  
      La coordenada x de la cancha a la que se va a mover el jugador. Si es menor a 0 se toma como 0 y si supera largo\_cancha se toma como largo\_cancha.  
    - `coord_y : float`  
      La coordenada y de la cancha a la que se va a mover el jugador. Si es menor a 0 se toma como 0 y si supera ancho\_cancha se toma como ancho\_cancha.

	El jugador se mueve hacia la coordenada (coord\_x, coord\_y) de la cancha.

	`Devuelve: Null`

### `patear(potencia: int):`  
  - Argumentos:   
	  - `potencia : int`  
      La potencia con la que va a patear el jugador. Si potencia es menor que 1, se toma como 1 y si es mayor que 100, se toma como 100\.

  Si el jugador tiene la pelota, la patea hacia adelante en la línea que forman la pelota y el jugador. La velocidad del disparo dependerá del parámetro potencia multiplicado por la estadística power del jugador. Si no la tiene, no hace nada.

  `Devuelve: Null`

### `patear_hacia(potencia: int, pos_x : int, pos_y : int):  `

  - Argumentos:   
	  - `potencia : int`  
      La potencia con la que va a patear el jugador. Si potencia es menor que 1, se toma como 1 y si es mayor que 100, se toma como 100\.  
	  - `coord_x : int`  
      Coordenada x de la cancha a la que la pelota se dirigirá. Si es menor a 0 se toma como 0 y si supera largo\_cancha se toma como largo\_cancha. 

	  - `coord_y : float`  
      Coordenada y de la cancha a la que la pelota se dirigirá. Si es menor a 0 se toma como 0 y si supera ancho\_cancha se toma como ancho\_cancha.

	Si el jugador tiene la pelota, la patea hacia (coord\_x, coord\_y). Si (coord\_x, coord\_y) se encuentra detrás del jugador (respecto a la línea que forman él y la pelota), patea hacia la coordenada (x, y) más cercana posible. La velocidad del disparo dependerá del parámetro potencia multiplicado por la estadística power del jugador. Si no la tiene, no hace nada.

  `Devuelve: Null`

### `pos_aliado(num : int) -> (int, int):`  
  - Argumentos:   
	  - `num : int`  
      El nùmero del jugador al comenzar el partido. 

  `Devuelve:` si el número está entre 1 y 3, devuelve dupla (x, y) que representa las coordenadas (x, y) en las que se encuentra el jugador aliado. Si el número no está entre 1 y 3, alza un error.

### `pos_rival(num: int) -> (int, int):`  
  - Argumentos:   
	  `num : int`  
      El número del jugador rival al comenzar el partido. 

  `Devuelve:` si el número está entre 1 y 3, tupla (x, y) que representa las coordenadas (x, y) en las que se encuentra el jugador rival. Si el numero no esta entre 1 y 3, alza un error.

### `tiene_rival_pelota() -> Bool:`  
  `Devuelve:` True si existe un rival que tiene la pelota, False si esto no ocurre

### `tiene_aliado_pelota() -> Bool:`  
  `Devuelve:` True si existe un aliado que tiene la pelota, False si esto no ocurre

### `tiene_nadie_pelota() -> Bool:`  
  `Devuelve:` True si no se cumple `tiene_rival_pelota()` ni `tiene_aliado_pelota()`, False si ocurre `tiene_rival_pelota()` o `tiene_aliado_pelota()`

### `posicion_pelota() -> (x: int, y: int):`  
  `Devuelve:` Coordenadas (x, y) donde se encuentra la pelota.

### `num_titular_mejor_stat(stat : String) -> (n: Int, aliado: Bool):` 
  `Devuelve:` El número del titular y True si es aliado que tenga más de una característica, si el string pasado en stat coincide con una estadística. Si no, alza un error.

### `tiempo_actual() -> (minutos : int, segundos : int):`
  `Devuelve:` Dupla (minutos : int, segundos : int), que representa los minutos y segundos transcurridos.

`tiempo_restante() -> (minutos : int, segundos : int):`  
  `Devuelve:` Dupla (minutos : int, segundos : int), que representa los minutos y segundos restantes.
