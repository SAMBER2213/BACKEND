from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from bson import ObjectId
from datetime import datetime
import hashlib
import os
from .db import get_db


def serializar(doc):
    if doc is None:
        return None
    doc['id'] = str(doc['_id'])
    del doc['_id']
    return doc


def hash_password(password):
    salt = os.urandom(16).hex()
    hashed = hashlib.sha256((password + salt).encode()).hexdigest()
    return f"{salt}:{hashed}"


def verify_password(password, stored):
    try:
        salt, hashed = stored.split(':')
        return hashlib.sha256((password + salt).encode()).hexdigest() == hashed
    except Exception:
        return False


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@api_view(['GET'])
def health(request):
    return Response({'status': 'ok', 'mensaje': 'API Planificador funcionando'})


# ─────────────────────────────────────────
# AUTH — REGISTRO Y LOGIN
# ─────────────────────────────────────────

@api_view(['POST'])
def registro(request):
    db = get_db()
    data = request.data
    errores = {}

    nombre = data.get('nombre', '').strip()
    apellido = data.get('apellido', '').strip()
    correo = data.get('correo', '').strip().lower()
    clave = data.get('clave', '')
    confirmar = data.get('confirmarClave', '')

    # Validaciones
    if not nombre:
        errores['nombre'] = 'El nombre es obligatorio'
    elif not nombre.replace(' ', '').isalpha():
        errores['nombre'] = 'El nombre solo puede contener letras'

    if not apellido:
        errores['apellido'] = 'El apellido es obligatorio'
    elif not apellido.replace(' ', '').isalpha():
        errores['apellido'] = 'El apellido solo puede contener letras'

    if not correo:
        errores['correo'] = 'El correo es obligatorio'
    elif '@' not in correo or '.' not in correo:
        errores['correo'] = 'El correo no es válido'

    if not clave:
        errores['clave'] = 'La clave es obligatoria'
    elif len(clave) < 6:
        errores['clave'] = 'La clave debe tener al menos 6 caracteres'

    if not confirmar:
        errores['confirmarClave'] = 'Debes confirmar la clave'
    elif clave and clave != confirmar:
        errores['confirmarClave'] = 'Las claves no coinciden'

    if errores:
        return Response({'error': 'Datos inválidos', 'campos': errores}, status=status.HTTP_400_BAD_REQUEST)

    # Verificar si ya existe el correo
    if db.usuarios.find_one({'correo': correo}):
        return Response({'error': 'Datos inválidos', 'campos': {'correo': 'Este correo ya está registrado'}}, status=status.HTTP_400_BAD_REQUEST)

    usuario = {
        'nombre': nombre,
        'apellido': apellido,
        'correo': correo,
        'clave': hash_password(clave),
        'creadoEn': datetime.utcnow().isoformat(),
    }

    resultado = db.usuarios.insert_one(usuario)
    usuario_id = str(resultado.inserted_id)

    return Response({
        'mensaje': 'Usuario registrado correctamente',
        'usuario': {
            'id': usuario_id,
            'nombre': nombre,
            'apellido': apellido,
            'correo': correo,
        }
    }, status=status.HTTP_201_CREATED)


@api_view(['POST'])
def login(request):
    db = get_db()
    data = request.data
    errores = {}

    correo = data.get('correo', '').strip().lower()
    clave = data.get('clave', '')

    if not correo:
        errores['correo'] = 'El correo es obligatorio'
    if not clave:
        errores['clave'] = 'La clave es obligatoria'

    if errores:
        return Response({'error': 'Datos inválidos', 'campos': errores}, status=status.HTTP_400_BAD_REQUEST)

    usuario = db.usuarios.find_one({'correo': correo})
    if not usuario or not verify_password(clave, usuario['clave']):
        return Response({'error': 'Correo o clave incorrectos', 'campos': {}}, status=status.HTTP_401_UNAUTHORIZED)

    return Response({
        'mensaje': 'Login exitoso',
        'usuario': {
            'id': str(usuario['_id']),
            'nombre': usuario['nombre'],
            'apellido': usuario['apellido'],
            'correo': usuario['correo'],
        }
    })


# ─────────────────────────────────────────
# ACTIVIDADES — filtradas por usuario
# ─────────────────────────────────────────

@api_view(['GET'])
def hoy(request):
    """
    GET /api/hoy/
    Devuelve las subtareas pendientes del usuario agrupadas en tres secciones:
      - vencidas: fecha < hoy, ordenadas por fecha ASC (más antigua primero)
      - hoy:      fecha == hoy, ordenadas por horas ASC (menor esfuerzo primero)
      - proximas: fecha > hoy o sin fecha, ordenadas por fecha ASC (sin fecha al final)

    Headers requeridos:
      X-Usuario-Id: <id del usuario autenticado>

    Response 200:
    {
      "fecha": "2025-06-10",
      "regla": "Vencidas → Hoy → Próximas. Desempate: menor esfuerzo primero.",
      "carga_hoy_horas": 3.5,
      "vencidas":  [ { subtarea }, ... ],
      "hoy":       [ { subtarea }, ... ],
      "proximas":  [ { subtarea }, ... ]
    }

    Cada subtarea incluye los campos originales más:
      actividadId, actividadTitulo, actividadCurso
    """
    db = get_db()
    usuario_id = request.headers.get('X-Usuario-Id', '')

    if not usuario_id:
        return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)

    ahora = datetime.utcnow()
    fecha_hoy = ahora.strftime('%Y-%m-%d')
    hora_actual = ahora.strftime('%H:%M')

    actividades_docs = list(db.actividades.find({'usuarioId': usuario_id}))

    vencidas, para_hoy, proximas = [], [], []

    for act in actividades_docs:
        act_id = str(act['_id'])
        act_titulo = act.get('titulo', '')
        act_curso = act.get('curso', '')

        for sub in act.get('subtareas', []):
            if sub.get('estado') == 'hecho':
                continue

            enriquecida = {
                **sub,
                'actividadId': act_id,
                'actividadTitulo': act_titulo,
                'actividadCurso': act_curso,
            }

            fecha_sub = sub.get('fecha', '')
            hora_sub = sub.get('hora', '')

            if not fecha_sub:
                proximas.append(enriquecida)
            elif fecha_sub < fecha_hoy:
                vencidas.append(enriquecida)
            elif fecha_sub == fecha_hoy:
                if hora_sub and hora_sub < hora_actual:
                    vencidas.append(enriquecida)
                else:
                    para_hoy.append(enriquecida)
            else:
                proximas.append(enriquecida)

    vencidas.sort(key=lambda s: s.get('fecha', ''))
    para_hoy.sort(key=lambda s: float(s.get('horas', 0)))
    proximas.sort(key=lambda s: (s.get('fecha', '') == '', s.get('fecha', '')))

    carga_hoy = sum(float(s.get('horas', 0)) for s in para_hoy)

    return Response({
        'fecha': fecha_hoy,
        'regla': 'Vencidas → Hoy → Próximas. Desempate: menor esfuerzo primero.',
        'carga_hoy_horas': round(carga_hoy, 2),
        'vencidas': vencidas,
        'hoy': para_hoy,
        'proximas': proximas,
    })


@api_view(['GET', 'POST'])
def actividades(request):
    db = get_db()
    usuario_id = request.headers.get('X-Usuario-Id', '')

    if not usuario_id:
        return Response({'error': 'No autenticado'}, status=status.HTTP_401_UNAUTHORIZED)

    if request.method == 'GET':
        docs = list(db.actividades.find({'usuarioId': usuario_id}))
        return Response([serializar(d) for d in docs])

    if request.method == 'POST':
        data = request.data
        errores = {}
        if not data.get('titulo', '').strip():
            errores['titulo'] = 'El título es obligatorio'
        if not data.get('tipo', '').strip():
            errores['tipo'] = 'El tipo es obligatorio'
        if not data.get('curso', '').strip():
            errores['curso'] = 'El curso es obligatorio'

        if errores:
            return Response({'error': 'Datos inválidos', 'campos': errores}, status=status.HTTP_400_BAD_REQUEST)

        nueva = {
            'usuarioId': usuario_id,
            'titulo': data['titulo'].strip(),
            'tipo': data['tipo'].strip(),
            'curso': data['curso'].strip(),
            'fechaLimite': data.get('fechaLimite', ''),
            'horasEstimadas': data.get('horasEstimadas', 0),
            'subtareas': [],
            'creadoEn': datetime.utcnow().isoformat(),
        }

        resultado = db.actividades.insert_one(nueva)
        nueva['id'] = str(resultado.inserted_id)
        del nueva['_id']
        return Response(nueva, status=status.HTTP_201_CREATED)


@api_view(['GET', 'PUT', 'DELETE'])
def actividad_detalle(request, actividad_id):
    db = get_db()
    usuario_id = request.headers.get('X-Usuario-Id', '')

    try:
        oid = ObjectId(actividad_id)
    except Exception:
        return Response({'error': 'ID inválido'}, status=status.HTTP_400_BAD_REQUEST)

    doc = db.actividades.find_one({'_id': oid, 'usuarioId': usuario_id})
    if not doc:
        return Response({'error': 'Actividad no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(serializar(doc))

    if request.method == 'PUT':
        data = request.data
        errores = {}
        if 'titulo' in data and not data['titulo'].strip():
            errores['titulo'] = 'El título no puede estar vacío'
        if 'curso' in data and not data['curso'].strip():
            errores['curso'] = 'El curso no puede estar vacío'

        if errores:
            return Response({'error': 'Datos inválidos', 'campos': errores}, status=status.HTTP_400_BAD_REQUEST)

        campos = {}
        for campo in ['titulo', 'tipo', 'curso', 'fechaLimite', 'horasEstimadas']:
            if campo in data:
                campos[campo] = data[campo]

        db.actividades.update_one({'_id': oid}, {'$set': campos})
        actualizado = db.actividades.find_one({'_id': oid})
        return Response(serializar(actualizado))

    if request.method == 'DELETE':
        db.actividades.delete_one({'_id': oid})
        return Response({'mensaje': 'Actividad eliminada correctamente'})


@api_view(['GET', 'POST'])
def subtareas(request, actividad_id):
    db = get_db()
    usuario_id = request.headers.get('X-Usuario-Id', '')

    try:
        oid = ObjectId(actividad_id)
    except Exception:
        return Response({'error': 'ID inválido'}, status=status.HTTP_400_BAD_REQUEST)

    doc = db.actividades.find_one({'_id': oid, 'usuarioId': usuario_id})
    if not doc:
        return Response({'error': 'Actividad no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'GET':
        return Response(doc.get('subtareas', []))

    if request.method == 'POST':
        data = request.data
        errores = {}
        if not data.get('nombre', '').strip():
            errores['nombre'] = 'El nombre es obligatorio'
        horas = data.get('horas', 0)
        try:
            horas = float(horas)
            if horas <= 0:
                errores['horas'] = 'Las horas deben ser mayor a 0'
        except (ValueError, TypeError):
            errores['horas'] = 'Las horas deben ser un número válido'

        if errores:
            return Response({'error': 'Datos inválidos', 'campos': errores}, status=status.HTTP_400_BAD_REQUEST)

        nueva_sub = {
            'id': str(ObjectId()),
            'nombre': data['nombre'].strip(),
            'fecha': data.get('fecha', ''),
            'hora': data.get('hora', ''),
            'horas': horas,
            'estado': 'pendiente',
            'nota': '',
            'creadoEn': datetime.utcnow().isoformat(),
        }

        db.actividades.update_one({'_id': oid}, {'$push': {'subtareas': nueva_sub}})
        return Response(nueva_sub, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'DELETE'])
def subtarea_detalle(request, actividad_id, subtarea_id):
    db = get_db()
    usuario_id = request.headers.get('X-Usuario-Id', '')

    try:
        oid = ObjectId(actividad_id)
    except Exception:
        return Response({'error': 'ID de actividad inválido'}, status=status.HTTP_400_BAD_REQUEST)

    doc = db.actividades.find_one({'_id': oid, 'usuarioId': usuario_id})
    if not doc:
        return Response({'error': 'Actividad no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    subtarea = next((s for s in doc.get('subtareas', []) if s['id'] == subtarea_id), None)
    if not subtarea:
        return Response({'error': 'Subtarea no encontrada'}, status=status.HTTP_404_NOT_FOUND)

    if request.method == 'PUT':
        data = request.data
        errores = {}
        if 'nombre' in data and not data['nombre'].strip():
            errores['nombre'] = 'El nombre no puede estar vacío'
        if 'horas' in data:
            try:
                if float(data['horas']) <= 0:
                    errores['horas'] = 'Las horas deben ser mayor a 0'
            except (ValueError, TypeError):
                errores['horas'] = 'Las horas deben ser un número válido'

        if errores:
            return Response({'error': 'Datos inválidos', 'campos': errores}, status=status.HTTP_400_BAD_REQUEST)

        for campo in ['nombre', 'fecha', 'hora', 'horas', 'estado', 'nota']:
            if campo in data:
                subtarea[campo] = data[campo]

        db.actividades.update_one(
            {'_id': oid, 'subtareas.id': subtarea_id},
            {'$set': {'subtareas.$': subtarea}}
        )
        return Response(subtarea)

    if request.method == 'DELETE':
        db.actividades.update_one({'_id': oid}, {'$pull': {'subtareas': {'id': subtarea_id}}})
        return Response({'mensaje': 'Subtarea eliminada correctamente'})