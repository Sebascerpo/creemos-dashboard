export interface Puesto {
    zona: string;
    cod_puesto: string;
    nombre: string;
    num_mesas: number;
}

export interface Municipio {
    cod: string;
    nombre: string;
    puestos: Puesto[];
}

export interface CandidatoCatalogo {
    cod_candidato: string;
    nombre_completo: string;
    es_lista: boolean;
}

export interface E14FormData {
    corporacion: 'senado' | 'camara';
    municipio: Municipio;
    puesto: Puesto;
    num_mesa: number;
    votos: Array<{ cod_candidato: string; votos: number }>;
}

export interface MesaReportada {
    mesa_key: string;
    cod_depto: string;
    cod_muni: string;
    nom_muni: string;
    zona: string;
    cod_puesto: string;
    nom_puesto: string;
    num_mesa: number;
    corporacion: string;
    corporacion_nombre: string;
    circunscripcion: string;
    cod_partido: string;
    registros_mmv: string[];
    total_votos: number;
    testigo_uid: string;
    testigo_email: string;
    timestamp?: unknown;
    estado: 'enviado';
}
