import { HttpClient } from '@angular/common/http';
import { Injectable, computed, inject, signal } from '@angular/core';
import { firstValueFrom } from 'rxjs';
import { CandidatoCatalogo, Municipio, Puesto } from '../models/catalogo.model';

interface CandidatosPayload {
    camara_antioquia: {
        corporacion: string;
        circunscripcion: string;
        cod_depto: string;
        partidos: Array<{ cod_partido: string; nombre: string }>;
        candidatos: CandidatoCatalogo[];
    };
}

interface DivipolPayload {
    depto: { cod: string; nombre: string };
    municipios: Municipio[];
}

@Injectable({ providedIn: 'root' })
export class CatalogoService {
    private readonly http = inject(HttpClient);

    private readonly divipolSig = signal<DivipolPayload | null>(null);
    private readonly candidatosSig = signal<CandidatosPayload | null>(null);
    private readonly loadedSig = signal(false);

    readonly loaded = computed(() => this.loadedSig());

    async init(): Promise<void> {
        if (this.loadedSig()) return;
        const [divipol, candidatos] = await Promise.all([
            firstValueFrom(this.http.get<DivipolPayload>('assets/data/divipol_antioquia.json')),
            firstValueFrom(this.http.get<CandidatosPayload>('assets/data/candidatos_creemos.json'))
        ]);
        this.divipolSig.set(divipol);
        this.candidatosSig.set(candidatos);
        this.loadedSig.set(true);
    }

    getMunicipios(): Municipio[] {
        return this.divipolSig()?.municipios ?? [];
    }

    getPuestosByMunicipio(codMuni: string): Puesto[] {
        const muni = this.getMunicipios().find((m) => m.cod === codMuni);
        return muni?.puestos ?? [];
    }

    getMesasByPuesto(codMuni: string, zona: string, codPuesto: string): number[] {
        const puesto = this.getPuestosByMunicipio(codMuni).find((p) => p.zona === zona && p.cod_puesto === codPuesto);
        const total = Math.max(0, Number(puesto?.num_mesas ?? 0));
        return Array.from({ length: total }, (_, i) => i + 1);
    }

    getCandidatosByCorporacion(_: 'camara' = 'camara'): CandidatoCatalogo[] {
        const payload = this.candidatosSig();
        if (!payload) return [];
        return payload.camara_antioquia.candidatos;
    }

    getPartidosCamara(): Array<{ cod_partido: string; nombre: string }> {
        return this.candidatosSig()?.camara_antioquia.partidos ?? [];
    }

    getCircunscripcion(_: 'camara' = 'camara'): string {
        const payload = this.candidatosSig();
        if (!payload) return '';
        return payload.camara_antioquia.circunscripcion;
    }

    getCandidatoNombreMap(_: 'camara' = 'camara'): Record<string, string> {
        const out: Record<string, string> = {};
        for (const c of this.getCandidatosByCorporacion('camara')) {
            out[`${c.cod_partido}_${c.cod_candidato}`] = c.nombre_completo;
        }
        return out;
    }

    getTotalMesasAntioquia(): number {
        return this.getMunicipios().reduce((acc, m) => acc + (m.puestos ?? []).reduce((a, p) => a + (Number(p.num_mesas) || 0), 0), 0);
    }
}
