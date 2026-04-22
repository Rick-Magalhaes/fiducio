from app.models.xp.xp_model import ProcuracaoXP
from app.models.instrucao.instrucao_btg import InstrucaoVoto

MODELOS = {
    "XP":  ProcuracaoXP,
    "BTG": ProcuracaoXP,  # provisório — mesma lógica por enquanto
    "BTGVoto": InstrucaoVoto, 
}