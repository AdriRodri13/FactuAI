from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .permissions import TieneAPIKey
from .serializers import OCRInputSerializer
from .procesador import ProcesadorOCR

class VistaExtraccionDatos(APIView):
    permission_classes = [TieneAPIKey]

    def post(self, request):
        serializador = OCRInputSerializer(data=request.data)
        if serializador.is_valid():
            texto_ocr = serializador.validated_data['texto_ocr']
            resultado = ProcesadorOCR.procesar_texto(texto_ocr)
            return Response({"estado": "exito", "resultado": resultado}, status=status.HTTP_200_OK)
        return Response(serializador.errors, status=status.HTTP_400_BAD_REQUEST)
