"""Comportamientos que recibe todo usuario nuevo.

Cada usuario recibe una copia propia de estos 3 behaviors al registrarse. El
código solo usa las primitivas y constantes de docs/API Comportamientos.md.
Entre los tres cubren las interacciones básicas del motor: ir a la pelota,
chocar con otro jugador y hacer rebotar la pelota contra el borde.
"""

FORWARD_CODE = """\
# Va a buscar la pelota y, si la tiene, patea al arco rival.
ball = ball_position()
if i_have_ball():
    me = my_position()
    goal = opponent_goal
    
    # Hacia dónde miro (de mí a la pelota) y hacia dónde quiero patear
    # (de la pelota al arco).
    forward = (ball[0] - me[0], ball[1] - me[1])
    to_goal = (goal[0] - ball[0], goal[1] - ball[1])
    
    # Si apuntan para lados opuestos (producto escalar negativo), el arco quedó
    # a mis espaldas y el motor patearía de costado: primero camino hacia el
    # arco para girar, y pateo en un tick siguiente.
    if (forward[0] * to_goal[0] + forward[1] * to_goal[1]) < 0:
        go_to(goal[0], goal[1])
    else:
        kick_to(goal[0], goal[1])
else:
    go_to(ball[0], ball[1])
"""

DEFENDER_CODE = """\
# Marca al delantero rival. Si la pelota se acerca, va a buscarla, y si la
# tiene, la despeja hacia adelante contra el lateral más cercano.
me = my_position()
ball = ball_position()
if i_have_ball():
    if me[1] < field_width / 2:
        target = (me[0] + 15, 0)
    else:
        target = (me[0] + 15, field_width)
    
    # Hacia dónde miro (de mí a la pelota) y hacia dónde quiero patear 
    # (de la pelota al destino).
    forward = (ball[0] - me[0], ball[1] - me[1])
    to_target = (target[0] - ball[0], target[1] - ball[1])
    
    # Si apuntan para lados opuestos (producto escalar negativo), el destino
    # quedó a mis espaldas y el motor patearía de costado: primero camino hacia
    # él para girar, y pateo en un tick siguiente.
    if (forward[0] * to_target[0] + forward[1] * to_target[1]) < 0:
        go_to(target[0], target[1])
    else:
        kick_to(target[0], target[1])
elif distance(me[0], me[1], ball[0], ball[1]) < 15:
    go_to(ball[0], ball[1])
else:
    rival = opponent_position(3)
    go_to(rival[0], rival[1])
"""

MIDFIELDER_CODE = """\
# Acompaña la jugada unos metros detrás de la pelota. Si la pelota está cerca
# y no la tiene un compañero, va a buscarla. Si la tiene, la tira en diagonal
# contra el lateral para que rebote hacia el arco rival.
me = my_position()
ball = ball_position()
if i_have_ball():
    if me[1] < field_width / 2:
        target = (me[0] + 25, 0)
    else:
        target = (me[0] + 25, field_width)
    
    # Hacia dónde miro (de mí a la pelota) y hacia dónde quiero patear 
    # (de la pelota al destino).
    forward = (ball[0] - me[0], ball[1] - me[1])
    to_target = (target[0] - ball[0], target[1] - ball[1])
    
    # Si apuntan para lados opuestos (producto escalar negativo), el destino
    # quedó a mis espaldas y el motor patearía de costado: primero camino hacia
    # él para girar, y pateo en un tick siguiente.
    if (forward[0] * to_target[0] + forward[1] * to_target[1]) < 0:
        go_to(target[0], target[1])
    else:
        kick_to(target[0], target[1])
elif teammate_has_ball():
    # Un compañero la lleva: acompaño unos metros detrás, sin disputársela.
    go_to(ball[0] - 10, ball[1])
elif distance(me[0], me[1], ball[0], ball[1]) < 20:
    # Nadie de mi equipo la tiene y está cerca: voy a buscarla.
    go_to(ball[0], ball[1])
else:
    # La pelota está lejos: me ubico detrás para acompañar la jugada.
    go_to(ball[0] - 10, ball[1])
"""

DEFAULT_BEHAVIORS = [
    {"name": "Delantero", "code": FORWARD_CODE},
    {"name": "Mediocampista", "code": MIDFIELDER_CODE},
    {"name": "Defensor", "code": DEFENDER_CODE},
]