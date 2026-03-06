from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status
from bson import ObjectId
from datetime import datetime
from .db import get_db


def serializar(doc):
    """Convierte ObjectId a string para poder enviar en JSON."""
    if doc is None:
        return None
    doc['id'] = str(doc['_id'])
    del doc['_id']
    return doc


# ─────────────────────────────────────────
# HEALTH CHECK
# ─────────────────────────────────────────

@api_view(['GET'])
def health(request):
    return Response({'status': 'ok', 'mensaje': 'API Planificador funcionando'})


# ─────────────────────────────────────────
# ACTIVIDADES
# ─────────────────────────────────────────

@api_view(['GET', 'POST'])
def actividades(request):
    db = get_db()

    if request.method == 'GET':
        docs = list(db.actividades.find())
        return Response([serializar(d) for d in docs])

    if request.method == 'POST':
        data = request.data

        # Validaciones
        errores = {}
        if not data.get('titulo', '').strip():
            errores['titulo'] = 'El título es obligatorio'
        if not data.get('tipo', '').strip():
            errores['tipo'] = 'El tipo es obligatorio'
        if not data.get('curso', '').strip():
            errores['curso'] = 'El curso es obligatorio'

        if errores:
            return Response(
                {'error': 'Datos inválidos', 'campos': errores},
                status=status.HTTP_400_BAD_REQUEST
            )

        nueva = {
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

    try:
        oid = ObjectId(actividad_id)
    except Exception:
        return Response({'error': 'ID inválido'}, status=status.HTTP_400_BAD_REQUEST)

    doc = db.actividades.find_one({'_id': oid})
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
            return Response(
                {'error': 'Datos inválidos', 'campos': errores},
                status=status.HTTP_400_BAD_REQUEST
            )

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


# ─────────────────────────────────────────
# SUBTAREAS
# ─────────────────────────────────────────

@api_view(['GET', 'POST'])
def subtareas(request, actividad_id):
    db = get_db()

    try:
        oid = ObjectId(actividad_id)
    except Exception:
        return Response({'error': 'ID inválido'}, status=status.HTTP_400_BAD_REQUEST)

    doc = db.actividades.find_one({'_id': oid})
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
            return Response(
                {'error': 'Datos inválidos', 'campos': errores},
                status=status.HTTP_400_BAD_REQUEST
            )

        nueva_sub = {
            'id': str(ObjectId()),
            'nombre': data['nombre'].strip(),
            'fecha': data.get('fecha', ''),
            'horas': horas,
            'estado': 'pendiente',
            'nota': '',
            'creadoEn': datetime.utcnow().isoformat(),
        }

        db.actividades.update_one(
            {'_id': oid},
            {'$push': {'subtareas': nueva_sub}}
        )

        return Response(nueva_sub, status=status.HTTP_201_CREATED)


@api_view(['PUT', 'DELETE'])
def subtarea_detalle(request, actividad_id, subtarea_id):
    db = get_db()

    try:
        oid = ObjectId(actividad_id)
    except Exception:
        return Response({'error': 'ID de actividad inválido'}, status=status.HTTP_400_BAD_REQUEST)

    doc = db.actividades.find_one({'_id': oid})
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
            return Response(
                {'error': 'Datos inválidos', 'campos': errores},
                status=status.HTTP_400_BAD_REQUEST
            )

        for campo in ['nombre', 'fecha', 'horas', 'estado', 'nota']:
            if campo in data:
                subtarea[campo] = data[campo]

        db.actividades.update_one(
            {'_id': oid, 'subtareas.id': subtarea_id},
            {'$set': {'subtareas.$': subtarea}}
        )
        return Response(subtarea)

    if request.method == 'DELETE':
        db.actividades.update_one(
            {'_id': oid},
            {'$pull': {'subtareas': {'id': subtarea_id}}}
        )
        return Response({'mensaje': 'Subtarea eliminada correctamente'})