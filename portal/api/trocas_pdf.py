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

        # Encontrar pasta "Trocas GNR"
        results = service.files().list(
            q="name='Trocas GNR' and mimeType='application/vnd.google-apps.folder' and trashed=false",
            fields="files(id)"
        ).execute()
        folders = results.get("files", [])
        folder_id = folders[0]["id"] if folders else None

        media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
        meta = {"name": filename, **({"parents": [folder_id]} if folder_id else {})}
        f = service.files().create(body=meta, media_body=media, fields="id, webViewLink").execute()
        return f.get("webViewLink")

    except Exception as e:
        logger.warning("Erro no upload Drive: %s", e)
        return None


def gerar_e_upload(data, nome_orig, serv_orig, nome_dest, serv_dest,
                   data_pedido="", data_aceitacao="", validador="", data_validacao="", admin_id=None):
    """Gera PDF, assina digitalmente com 3 campos e faz upload para o Drive."""
    pdf = gerar_pdf_troca(data, nome_orig, serv_orig, nome_dest, serv_dest,
                          data_pedido, data_aceitacao, validador, data_validacao)
    if pdf:
        # Assinar com 3 campos — solicitante, aceitante e validador
        pdf = assinar_pdf(
            pdf,
            validador=validador or "Admin",
            data_validacao=data_validacao or "",
            nome_orig=nome_orig or "",
            data_pedido=data_pedido or "",
            nome_dest=nome_dest or "",
            data_aceitacao=data_aceitacao or "",
        )
        filename = f"Troca_{data.replace('/','_')}_{nome_orig.split()[-1]}_{nome_dest.split()[-1]}.pdf"
        return upload_drive(pdf, filename, admin_id=admin_id or "1030")
    return None


def gerar_certificado_gnr() -> bytes:
    """Gera certificado auto-assinado da GNR em formato PKCS12."""
    import os
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.backends import default_backend
    import datetime

    # Usar certificado existente se guardado em variável de ambiente
    cert_b64 = os.environ.get("GNR_SIGNING_CERT_P12_B64")
    if cert_b64:
        import base64
        return base64.b64decode(cert_b64)

    # Gerar novo certificado
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "PT"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "GNR - Posto Territorial de Famalicão"),
        x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Portal de Escalas"),
        x509.NameAttribute(NameOID.COMMON_NAME, "GNR Famalicão - Assinatura Digital"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + datetime.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256(), default_backend())
    )
    p12 = pkcs12.serialize_key_and_certificates(
        name=b"GNR Portal Escalas",
        key=key, cert=cert, cas=None,
        encryption_algorithm=serialization.NoEncryption()
    )
    return p12


def assinar_pdf(pdf_bytes: bytes, validador: str, data_validacao: str,
                nome_orig: str = "", data_pedido: str = "",
                nome_dest: str = "", data_aceitacao: str = "") -> bytes:
    """Assina digitalmente o PDF com 3 campos — solicitante, aceitante e validador."""
    try:
        import io, asyncio
        from pyhanko.sign import signers, fields
        from pyhanko.pdf_utils import incremental_writer
        from pyhanko.sign.fields import SigFieldSpec

        p12_bytes = gerar_certificado_gnr()

        # Definir os 3 campos de assinatura (na última página, em rodapé)
        # Box: (x1, y1, x2, y2) em pontos — página A4 = 595 x 842 pts
        sig_fields = [
            SigFieldSpec(
                sig_field_name="Assinatura_Solicitante",
                on_page=-1,
                box=(36, 36, 190, 90),
            ),
            SigFieldSpec(
                sig_field_name="Assinatura_Aceitante",
                on_page=-1,
                box=(203, 36, 357, 90),
            ),
            SigFieldSpec(
                sig_field_name="Assinatura_Validador",
                on_page=-1,
                box=(370, 36, 559, 90),
            ),
        ]

        # Adicionar campos ao PDF
        w = incremental_writer.IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
        for sf in sig_fields:
            fields.append_signature_field(w, sf)

        # Guardar PDF com campos adicionados
        buf = io.BytesIO()
        w.write(buf)
        pdf_com_campos = buf.getvalue()

        # Assinar sequencialmente os 3 campos
        assinaturas = [
            {
                "field": "Assinatura_Solicitante",
                "reason": f"Solicitado por {nome_orig}",
                "signer_name": f"{nome_orig}",
                "data": data_pedido,
            },
            {
                "field": "Assinatura_Aceitante",
                "reason": f"Aceite por {nome_dest}",
                "signer_name": f"{nome_dest}",
                "data": data_aceitacao,
            },
            {
                "field": "Assinatura_Validador",
                "reason": f"Validado por {validador}",
                "signer_name": f"{validador}",
                "data": data_validacao,
                "certify": True,
            },
        ]

        pdf_atual = pdf_com_campos
        for assin in assinaturas:
            try:
                signer = signers.SimpleSigner.load_pkcs12(
                    pfx_file=p12_bytes,
                    passphrase=None,
                )
                w2 = incremental_writer.IncrementalPdfFileWriter(io.BytesIO(pdf_atual))
                meta = signers.PdfSignatureMetadata(
                    field_name=assin["field"],
                    reason=assin["reason"],
                    location="Posto Territorial de Famalicão",
                    signer_name=f"GNR Famalicão — {assin['signer_name']}",
                    certify=assin.get("certify", False),
                )
                out2 = io.BytesIO()
                asyncio.run(signers.async_sign_pdf(w2, meta, signer=signer, output=out2))
                pdf_atual = out2.getvalue()
            except Exception as e_sig:
                logger.warning("Erro ao assinar campo %s: %s", assin["field"], e_sig)

        return pdf_atual

    except Exception as e:
        logger.warning("Erro ao assinar PDF: %s", e)
        return pdf_bytes  # Devolver PDF sem assinatura se falhar
