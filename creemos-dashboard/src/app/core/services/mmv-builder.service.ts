import { Injectable } from '@angular/core';
import { E14FormData } from '../models/catalogo.model';

@Injectable({ providedIn: 'root' })
export class MmvBuilderService {
    private pad(value: string | number, length: number): string {
        return String(value).padStart(length, '0');
    }

    buildMesaKey(codMuni: string, zona: string, codPuesto: string, numMesa: number): string {
        return `01_${this.pad(codMuni, 3)}_${this.pad(zona, 2)}_${this.pad(codPuesto, 2)}_${this.pad(numMesa, 6)}`;
    }

    validateRecord(record: string): boolean {
        if (record.length !== 38) return false;
        const identificacion = record.slice(0, 30);
        const votos = record.slice(30, 38);
        return /^[0-9A-Za-z]{30}$/.test(identificacion) && /^[0-9]{8}$/.test(votos);
    }

    buildRecords(formData: E14FormData, circunscripcion: string, codPartido: string): string[] {
        const out: string[] = [];
        for (const item of formData.votos) {
            const votos = Math.max(0, Number(item.votos) || 0);
            if (votos <= 0) continue;
            const record =
                '01' +
                this.pad(formData.municipio.cod, 3) +
                this.pad(formData.puesto.zona, 2).toUpperCase() +
                this.pad(formData.puesto.cod_puesto, 2).toUpperCase() +
                this.pad(formData.num_mesa, 6) +
                '00' +
                '9999' +
                circunscripcion +
                this.pad(codPartido, 5) +
                this.pad(item.cod_candidato, 3) +
                this.pad(votos, 8);
            if (!this.validateRecord(record)) {
                throw new Error(`Registro MMV invalido para candidato ${item.cod_candidato}`);
            }
            out.push(record);
        }
        return out;
    }
}
