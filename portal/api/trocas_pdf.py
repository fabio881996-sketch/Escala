"""Geração de PDF de troca de serviço e upload para Google Drive."""
from __future__ import annotations
import io, os, base64, tempfile, logging
from datetime import datetime

logger = logging.getLogger(__name__)


def gerar_pdf_troca(
    data: str, nome_orig: str, serv_orig: str,
    nome_dest: str, serv_dest: str,
    data_pedido: str = "", data_aceitacao: str = "",
    validador: str = "", data_validacao: str = "",
) -> bytes | None:
    """Gera PDF de troca. Devolve bytes ou None se falhar."""
    try:
        from reportlab.pdfgen import canvas as _canvas
        from reportlab.lib.pagesizes import A4
        from reportlab.lib.units import mm
        from reportlab.lib.colors import HexColor
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont

        try:
            pdfmetrics.registerFont(TTFont('DV', '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'))
            pdfmetrics.registerFont(TTFont('DV-B', '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'))
            fn, fb = 'DV', 'DV-B'
        except Exception:
            fn, fb = 'Helvetica', 'Helvetica-Bold'

        buf = io.BytesIO()
        cv = _canvas.Canvas(buf, pagesize=A4)
        w, h = A4
        y = h - 10*mm

        # Cabeçalho
        _cab = os.environ.get("PDF_CABECALHO_B64", "")
        if _cab:
            try:
                _cb = base64.b64decode(_cab)
                with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as tf:
                    tf.write(_cb); cp = tf.name
                cw = 95*mm; ch = cw * (235/398)
                cv.drawImage(cp, 20*mm, h-8*mm-ch, width=cw, height=ch, preserveAspectRatio=True)
                os.unlink(cp)
                cv.setFillColor(HexColor('#000000')); cv.setFont(fb, 14)
                cv.drawString(20*mm+cw+10*mm, h-8*mm-ch/2, "TROCA DE SERVIÇO")
                y = h - 8*mm - ch - 10*mm
            except Exception:
                cv.setFont(fb, 14); cv.drawCentredString(w/2, h-20*mm, "TROCA DE SERVIÇO")
                y = h - 35*mm
        else:
            cv.setFont(fb, 14); cv.drawCentredString(w/2, h-20*mm, "TROCA DE SERVIÇO")
            y = h - 35*mm

        # Linha separadora
        cv.setStrokeColor(HexColor('#0f2540')); cv.setLineWidth(1.5)
        cv.line(20*mm, y, w-20*mm, y); y -= 12*mm

        # Dados da troca
        def row(label, value, yy):
            cv.setFont(fb, 9); cv.setFillColor(HexColor('#6c757d'))
            cv.drawString(20*mm, yy, label.upper())
            cv.setFont(fn, 10); cv.setFillColor(HexColor('#212529'))
            cv.drawString(70*mm, yy, value)
            return yy - 8*mm

        y = row("Data da Troca", data, y)
        y -= 3*mm
        y = row("Militar A", nome_orig, y)
        y = row("Cede o serviço", serv_orig, y)
        y -= 3*mm
        y = row("Militar B", nome_dest, y)
        y = row("Cede o serviço", serv_dest, y)
        y -= 6*mm

        cv.setStrokeColor(HexColor('#dee2e6')); cv.setLineWidth(0.5)
        cv.line(20*mm, y, w-20*mm, y); y -= 8*mm

        y = row("Data do Pedido", data_pedido, y)
        y = row("Data de Aceitação", data_aceitacao, y)
        y = row("Validado por", validador, y)
        y = row("Data de Validação", data_validacao, y)
        y -= 8*mm

        # Assinaturas
        cv.setFont(fb, 9); cv.setFillColor(HexColor('#6c757d'))
        cv.drawString(20*mm, y, "ASSINATURA MILITAR A")
        cv.drawString(110*mm, y, "ASSINATURA MILITAR B")
        y -= 20*mm
        cv.setLineWidth(0.5)
        cv.line(20*mm, y, 85*mm, y)
        cv.line(110*mm, y, 175*mm, y)

        # Rodapé
        cv.setFont(fn, 7); cv.setFillColor(HexColor('#adb5bd'))
        cv.drawRightString(w-20*mm, 12*mm, "Portal de Escalas GNR — Posto Territorial de Famalicão")

        cv.save()
        return buf.getvalue()

    except Exception as e:
        logger.warning("Erro a gerar PDF troca: %s", e)
        return None


def upload_drive(pdf_bytes: bytes, filename: str) -> str | None:
    """Faz upload do PDF para a pasta 'Trocas GNR' no Drive. Devolve URL ou None."""
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
        import json

        creds_json = os.environ.get("GOOGLE_CREDENTIALS_JSON", os.environ.get("gcp_service_account", ""))
        if not creds_json:
            return None

        creds_data = json.loads(creds_json)
        creds = service_account.Credentials.from_service_account_info(
            creds_data, scopes=["https://www.googleapis.com/auth/drive"]
        )
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        # ID fixo da pasta "Trocas GNR" partilhada com o service account
        folder_id = "1eiEHKvy9QtJCgVcJmhZl2Zu9o6IG5Wjl"

        media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
        meta = {"name": filename, "parents": [folder_id]}
        f = service.files().create(
            body=meta,
            media_body=media,
            fields="id, webViewLink",
            supportsAllDrives=True
        ).execute()
        return f.get("webViewLink")

    except Exception as e:
        logger.warning("Erro no upload Drive: %s", e)
        return None


def gerar_e_upload(data, nome_orig, serv_orig, nome_dest, serv_dest,
                   data_pedido="", data_aceitacao="", validador="", data_validacao=""):
    """Gera PDF e faz upload para o Drive."""
    pdf = gerar_pdf_troca(data, nome_orig, serv_orig, nome_dest, serv_dest,
                          data_pedido, data_aceitacao, validador, data_validacao)
    if pdf:
        filename = f"Troca_{data.replace('/','_')}_{nome_orig.split()[-1]}_{nome_dest.split()[-1]}.pdf"
        return upload_drive(pdf, filename)
    return None
