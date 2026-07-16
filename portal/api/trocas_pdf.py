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

        buf = io.BytesIO()
        W, H = A4
        c = _canvas.Canvas(buf, pagesize=A4)
        AZUL = HexColor("#0f2540")
        AZUL_V = HexColor("#1d6fa8")
        CINZA = HexColor("#64748b")
        LM = 20*mm

        # Cabeçalho
        c.setFillColor(AZUL)
        c.rect(0, H-28*mm, W, 28*mm, fill=1, stroke=0)
        c.setFillColor(HexColor("#ffffff"))
        c.setFont("Helvetica-Bold", 13)
        c.drawCentredString(W/2, H-12*mm, "GUARDA NACIONAL REPUBLICANA")
        c.setFont("Helvetica", 9)
        c.drawCentredString(W/2, H-19*mm, "Posto Territorial de Vila Nova de Famalicão")
        c.setFont("Helvetica-Bold", 11)
        c.drawCentredString(W/2, H-25*mm, "TROCA DE SERVIÇO")

        y = H - 38*mm

        # Data
        c.setFillColor(AZUL)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(LM, y, f"Data do serviço:  {data}")
        y -= 12*mm

        # Box militares
        def draw_box(y_pos, label, nome, cede, fica, data_acao):
            c.setFillColor(HexColor("#f0f4f8"))
            c.rect(LM, y_pos-30*mm, (W-2*LM)/2-3*mm, 30*mm, fill=1, stroke=0)
            c.setStrokeColor(AZUL_V)
            c.setLineWidth(0.5)
            c.rect(LM, y_pos-30*mm, (W-2*LM)/2-3*mm, 30*mm, fill=0, stroke=1)
            x = LM + 4*mm
            c.setFillColor(AZUL_V)
            c.setFont("Helvetica-Bold", 8)
            c.drawString(x, y_pos-5*mm, label)
            c.setFillColor(AZUL)
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x, y_pos-11*mm, nome)
            c.setFillColor(CINZA)
            c.setFont("Helvetica", 8)
            c.drawString(x, y_pos-17*mm, f"Cede:  {cede}")
            c.setFillColor(HexColor("#16a34a"))
            c.setFont("Helvetica-Bold", 8)
            c.drawString(x, y_pos-23*mm, f"Fica com:  {fica}")
            c.setFillColor(CINZA)
            c.setFont("Helvetica", 7.5)
            c.drawString(x, y_pos-28*mm, data_acao)

        draw_box(y, "🙋 SOLICITA", nome_orig, serv_orig, serv_dest, f"Pedido: {data_pedido}")
        x2 = LM + (W-2*LM)/2 + 3*mm
        c.setFillColor(HexColor("#f0f4f8"))
        c.rect(x2, y-30*mm, (W-2*LM)/2-3*mm, 30*mm, fill=1, stroke=0)
        c.setStrokeColor(HexColor("#16a34a"))
        c.rect(x2, y-30*mm, (W-2*LM)/2-3*mm, 30*mm, fill=0, stroke=1)
        c.setFillColor(HexColor("#16a34a"))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x2+4*mm, y-5*mm, "✅ ACEITA")
        c.setFillColor(AZUL)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x2+4*mm, y-11*mm, nome_dest)
        c.setFillColor(CINZA)
        c.setFont("Helvetica", 8)
        c.drawString(x2+4*mm, y-17*mm, f"Cede:  {serv_dest}")
        c.setFillColor(HexColor("#16a34a"))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(x2+4*mm, y-23*mm, f"Fica com:  {serv_orig}")
        c.setFillColor(CINZA)
        c.setFont("Helvetica", 7.5)
        c.drawString(x2+4*mm, y-28*mm, f"Aceite: {data_aceitacao}")

        y -= 36*mm

        # Validação
        c.setFillColor(HexColor("#fef3c7"))
        c.rect(LM, y-18*mm, W-2*LM, 18*mm, fill=1, stroke=0)
        c.setStrokeColor(HexColor("#d97706"))
        c.rect(LM, y-18*mm, W-2*LM, 18*mm, fill=0, stroke=1)
        c.setFillColor(HexColor("#92400e"))
        c.setFont("Helvetica-Bold", 8)
        c.drawString(LM+4*mm, y-5*mm, "⚖️ VALIDAÇÃO ADMINISTRATIVA")
        c.setFont("Helvetica", 8)
        c.drawString(LM+4*mm, y-11*mm, f"Validado por:  {validador}")
        c.drawString(LM+4*mm, y-16*mm, f"Data:  {data_validacao}")

        y -= 24*mm

        # Espaço para assinaturas com labels
        c.setFillColor(AZUL)
        c.setFont("Helvetica-Bold", 9)
        c.drawString(LM, y, "ASSINATURAS DIGITAIS")
        y -= 2*mm
        c.setStrokeColor(AZUL)
        c.setLineWidth(0.5)
        c.line(LM, y, W-LM, y)
        y -= 4*mm

        # Labels dos 3 signatários
        col_w = (W - 2*LM) / 3
        labels = [
            ("⚖️ VALIDADOR", validador),
            ("🙋 SOLICITANTE", nome_orig),
            ("✅ ACEITANTE", nome_dest),
        ]
        for i, (lbl, nome) in enumerate(labels):
            x_col = LM + i * col_w
            c.setFillColor(HexColor("#f0f4f8"))
            c.rect(x_col, y-22*mm, col_w-2*mm, 22*mm, fill=1, stroke=0)
            c.setStrokeColor(AZUL_V)
            c.setLineWidth(0.4)
            c.rect(x_col, y-22*mm, col_w-2*mm, 22*mm, fill=0, stroke=1)
            c.setFillColor(AZUL_V)
            c.setFont("Helvetica-Bold", 7)
            c.drawString(x_col+2*mm, y-5*mm, lbl)
            c.setFillColor(AZUL)
            c.setFont("Helvetica", 7.5)
            # Wrap nome se longo
            nome_curto = nome[:30] + "..." if len(nome) > 30 else nome
            c.drawString(x_col+2*mm, y-10*mm, nome_curto)
            c.setFillColor(CINZA)
            c.setFont("Helvetica", 6.5)
            c.drawString(x_col+2*mm, y-15*mm, "Assinado digitalmente")
            c.drawString(x_col+2*mm, y-19*mm, "GNR Posto Famalicão")

        y -= 28*mm  # espaço para os campos de assinatura

        # Rodapé
        c.setFillColor(CINZA)
        c.setFont("Helvetica", 7)
        c.drawCentredString(W/2, 12*mm, f"Documento gerado em {datetime.now().strftime('%d/%m/%Y %H:%M')} — Portal de Escalas GNR")

        c.save()
        return buf.getvalue()
    except Exception as e:
        logger.warning("Erro ao gerar PDF troca: %s", e)
        return None


def upload_drive(pdf_bytes: bytes, filename: str, admin_id: str | None = None) -> str | None:
    """Faz upload do PDF para a pasta 'Trocas GNR' no Drive usando OAuth do admin."""
    try:
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseUpload
        from google.oauth2.credentials import Credentials
        import json, time

        if not admin_id:
            admin_id = "1030"

        from portal.api.calendar import _get_token, _refresh_token, _guardar_token
        token_data = _get_token(admin_id)
        if not token_data:
            logger.warning("Upload Drive: admin %s não tem token OAuth", admin_id)
            return None

        # Refresh se necessário
        if time.time() > token_data.get("expires_at", 0) - 60:
            try:
                token_data = _refresh_token(token_data)
                token_data["expires_at"] = time.time() + token_data.get("expires_in", 3600)
                _guardar_token(admin_id, token_data)
            except Exception as e:
                logger.warning("Upload Drive: refresh token falhou: %s", e)
                return None

        creds = Credentials(token=token_data["access_token"])
        service = build("drive", "v3", credentials=creds, cache_discovery=False)

        folder_id = "1eiEHKvy9QtJCgVcJmhZl2Zu9o6IG5Wjl"
        media = MediaIoBaseUpload(io.BytesIO(pdf_bytes), mimetype="application/pdf")
        meta = {"name": filename, "parents": [folder_id]}
        f = service.files().create(body=meta, media_body=media, fields="id, webViewLink").execute()
        return f.get("webViewLink")

    except Exception as e:
        logger.warning("Erro no upload Drive: %s", e)
        return None


def gerar_certificado_gnr() -> bytes:
    """Gera certificado auto-assinado da GNR em formato PKCS12."""
    cert_b64 = os.environ.get("GNR_SIGNING_CERT_P12_B64", "").strip()
    if cert_b64:
        try:
            return base64.b64decode(cert_b64)
        except Exception:
            pass

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.hazmat.primitives.serialization import pkcs12
    from cryptography.hazmat.backends import default_backend
    import datetime as _dt

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048, backend=default_backend())
    subject = issuer = x509.Name([
        x509.NameAttribute(NameOID.COUNTRY_NAME, "PT"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "GNR - Posto Territorial de Famalicão"),
        x509.NameAttribute(NameOID.COMMON_NAME, "GNR Famalicão - Assinatura Digital"),
    ])
    now = _dt.datetime.now(_dt.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(subject).issuer_name(issuer)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now)
        .not_valid_after(now + _dt.timedelta(days=3650))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256(), default_backend())
    )
    p12 = pkcs12.serialize_key_and_certificates(
        name=b"GNR Portal Escalas", key=key, cert=cert, cas=None,
        encryption_algorithm=serialization.NoEncryption()
    )
    return p12


def assinar_pdf(pdf_bytes: bytes, validador: str, data_validacao: str,
                nome_orig: str = "", data_pedido: str = "",
                nome_dest: str = "", data_aceitacao: str = "") -> bytes:
    """Assina digitalmente o PDF com 3 campos — validador, solicitante e aceitante."""
    try:
        import asyncio as _asyncio, concurrent.futures
        from pyhanko.sign import signers, fields
        from pyhanko.pdf_utils import incremental_writer
        from pyhanko.sign.fields import SigFieldSpec

        p12_bytes = gerar_certificado_gnr()

        # Campos de assinatura com labels visíveis
        sig_fields = [
            SigFieldSpec(sig_field_name="Assinatura_Validador",   on_page=-1, box=(36,  36, 190, 90)),
            SigFieldSpec(sig_field_name="Assinatura_Solicitante", on_page=-1, box=(203, 36, 357, 90)),
            SigFieldSpec(sig_field_name="Assinatura_Aceitante",   on_page=-1, box=(370, 36, 559, 90)),
        ]

        # Adicionar campos ao PDF
        w = incremental_writer.IncrementalPdfFileWriter(io.BytesIO(pdf_bytes))
        for sf in sig_fields:
            fields.append_signature_field(w, sf)

        # Adicionar labels de texto por cima dos campos de assinatura
        from reportlab.pdfgen import canvas as _rc
        from reportlab.lib.pagesizes import A4 as _A4
        from reportlab.lib.units import mm as _mm
        _buf_lbl = io.BytesIO()
        _c_lbl = _rc.Canvas(_buf_lbl, pagesize=_A4)
        _W, _H = _A4
        _c_lbl.setFont("Helvetica", 6.5)
        _c_lbl.setFillColorRGB(0.06, 0.15, 0.25)
        _c_lbl.drawString(36/72*25.4*_mm/25.4*72,  92, f"VALIDADOR: {validador}")
        _c_lbl.drawString(203/72*25.4*_mm/25.4*72, 92, f"SOLICITANTE: {nome_orig}")
        _c_lbl.drawString(370/72*25.4*_mm/25.4*72, 92, f"ACEITANTE: {nome_dest}")
        _c_lbl.save()
        buf = io.BytesIO()
        w.write(buf)
        pdf_com_campos = buf.getvalue()

        # Assinar sequencialmente — Validador primeiro (certify=True)
        assinaturas = [
            {"field": "Assinatura_Validador",   "reason": f"Validado por {validador}",    "certify": True},
            {"field": "Assinatura_Solicitante", "reason": f"Solicitado por {nome_orig}",  "certify": False},
            {"field": "Assinatura_Aceitante",   "reason": f"Aceite por {nome_dest}",      "certify": False},
        ]

        pdf_atual = pdf_com_campos
        for assin in assinaturas:
            try:
                import tempfile as _tmp, os as _os
                with _tmp.NamedTemporaryFile(suffix='.p12', delete=False) as _f:
                    _f.write(p12_bytes)
                    _tmp_path = _f.name
                try:
                    signer = signers.SimpleSigner.load_pkcs12(pfx_file=_tmp_path, passphrase=None)
                finally:
                    _os.unlink(_tmp_path)

                w2 = incremental_writer.IncrementalPdfFileWriter(io.BytesIO(pdf_atual))
                meta = signers.PdfSignatureMetadata(
                    field_name=assin["field"],
                    reason=assin["reason"],
                    location="Posto Territorial de Famalicão",
                    certify=assin["certify"],
                )
                out2 = io.BytesIO()

                def _sign_in_thread():
                    loop = _asyncio.new_event_loop()
                    _asyncio.set_event_loop(loop)
                    try:
                        loop.run_until_complete(
                            signers.async_sign_pdf(w2, meta, signer=signer, output=out2)
                        )
                    finally:
                        loop.close()

                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(_sign_in_thread).result(timeout=30)

                pdf_atual = out2.getvalue()
            except Exception as e_sig:
                logger.warning("Erro ao assinar campo %s: %s", assin["field"], e_sig)

        return pdf_atual

    except Exception as e:
        logger.warning("Erro ao assinar PDF: %s", e)
        return pdf_bytes


def gerar_e_upload(data, nome_orig, serv_orig, nome_dest, serv_dest,
                   data_pedido="", data_aceitacao="", validador="", data_validacao="", admin_id=None):
    """Gera PDF, assina digitalmente com 3 campos e faz upload para o Drive."""
    pdf = gerar_pdf_troca(data, nome_orig, serv_orig, nome_dest, serv_dest,
                          data_pedido, data_aceitacao, validador, data_validacao)
    if pdf:
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
