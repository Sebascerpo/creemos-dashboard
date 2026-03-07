import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { CatalogoService } from '../core/services/catalogo.service';
import { FirestoreService } from '../core/services/firestore.service';

interface TrackingRow {
    codMuni: string;
    nomMuni: string;
    totalMesas: number;
    mesasReportadas: number;
    avancePct: number;
    ultimas24h: number;
}

@Component({
    selector: 'app-tracking',
    standalone: true,
    imports: [CommonModule],
    templateUrl: './tracking.component.html'
})
export class TrackingComponent {
    private readonly catalogo = inject(CatalogoService);
    private readonly firestore = inject(FirestoreService);

    private readonly nowMs = Date.now();

    readonly mesas = toSignal(this.firestore.getMesasReportadas(), { initialValue: [] });
    readonly expandedMuni = signal<string | null>(null);

    private uniqueMesaKeys(rows: any[]): number {
        return new Set(rows.map((r: any) => String(r.mesa_key ?? ''))).size;
    }

    readonly totalMesasAntioquia = computed(() => this.catalogo.getTotalMesasAntioquia());
    readonly mesasReportadas = computed(() => this.uniqueMesaKeys(this.mesas()));
    readonly avancePct = computed(() => {
        const total = this.totalMesasAntioquia();
        return total > 0 ? (this.mesasReportadas() / total) * 100 : 0;
    });
    readonly reportadas24h = computed(() => {
        const limit = this.nowMs - 24 * 60 * 60 * 1000;
        return this.mesas().filter((m: any) => {
            const ts = (m.timestamp as any)?.toDate?.() ?? (m.timestamp ? new Date(m.timestamp) : null);
            return ts instanceof Date && !Number.isNaN(ts.getTime()) && ts.getTime() >= limit;
        }).length;
    });

    readonly rows = computed<TrackingRow[]>(() => {
        const municipios = this.catalogo.getMunicipios();
        const reportes = this.mesas();
        return municipios
            .map((m) => {
                const totalMesas = (m.puestos ?? []).reduce((acc, p) => acc + (Number(p.num_mesas) || 0), 0);
                const items = reportes.filter((r: any) => r.cod_muni === m.cod);
                const mesasUnicas = this.uniqueMesaKeys(items);
                const ultimas24h = items.filter((r: any) => {
                    const ts = (r.timestamp as any)?.toDate?.() ?? (r.timestamp ? new Date(r.timestamp) : null);
                    return ts instanceof Date && !Number.isNaN(ts.getTime()) && ts.getTime() >= this.nowMs - 24 * 60 * 60 * 1000;
                }).length;
                return {
                    codMuni: m.cod,
                    nomMuni: m.nombre,
                    totalMesas,
                    mesasReportadas: mesasUnicas,
                    avancePct: totalMesas > 0 ? (mesasUnicas / totalMesas) * 100 : 0,
                    ultimas24h
                };
            })
            .sort((a, b) => b.avancePct - a.avancePct);
    });

    rowsDetalle = computed(() => {
        const cod = this.expandedMuni();
        if (!cod) return [];
        return this.mesas()
            .filter((m: any) => m.cod_muni === cod)
            .sort((a: any, b: any) => Number(a.num_mesa) - Number(b.num_mesa))
            .map((m: any) => ({
                ...m,
                timestampText: this.formatTimestamp(m.timestamp)
            }));
    });

    toggleExpand(codMuni: string): void {
        this.expandedMuni.set(this.expandedMuni() === codMuni ? null : codMuni);
    }

    private formatTimestamp(value: unknown): string {
        const raw = (value as any)?.toDate?.() ?? value;
        const date = raw instanceof Date ? raw : new Date(raw as any);
        if (Number.isNaN(date.getTime())) return '-';
        return date.toLocaleString('es-CO', { hour12: false });
    }
}
