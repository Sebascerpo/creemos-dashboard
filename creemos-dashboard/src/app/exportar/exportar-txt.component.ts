import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { ButtonModule } from 'primeng/button';
import { MessageModule } from 'primeng/message';
import { TableModule } from 'primeng/table';
import { MesaReportada } from '../core/models/catalogo.model';
import { FirestoreService } from '../core/services/firestore.service';
import { MmvBuilderService } from '../core/services/mmv-builder.service';

@Component({
    selector: 'app-exportar-txt',
    standalone: true,
    imports: [CommonModule, ButtonModule, TableModule, MessageModule],
    templateUrl: './exportar-txt.component.html'
})
export class ExportarTxtComponent {
    private readonly firestore = inject(FirestoreService);
    private readonly mmvBuilder = inject(MmvBuilderService);

    readonly docsFirebase = toSignal(this.firestore.getMesasReportadas(), { initialValue: [] as MesaReportada[] });
    readonly mensaje = signal('');
    readonly error = signal('');

    readonly docsFiltrados = computed(() => this.docsFirebase().filter((d) => String(d.corporacion ?? '') === '002'));

    readonly totalVotos = computed(() => this.docsFiltrados().reduce((acc, d) => acc + (Number(d.total_votos) || 0), 0));

    readonly registros = computed(() => {
        const docsOrdenados = [...this.docsFiltrados()].sort((a, b) => (a.mesa_key ?? '').localeCompare(b.mesa_key ?? ''));
        const validos: string[] = [];
        let invalidos = 0;

        for (const d of docsOrdenados) {
            const lineas = d.registros_mmv ?? [];
            for (const linea of lineas) {
                if (this.mmvBuilder.validateRecord(linea)) {
                    validos.push(linea);
                } else {
                    invalidos += 1;
                }
            }
        }

        return { validos, invalidos };
    });

    readonly preview = computed(() => this.registros().validos.slice(0, 120));

    get timestampActualizacion(): string {
        return new Date().toLocaleString('es-CO', { hour12: false });
    }

    formatTimestamp(value: unknown): string {
        const raw = (value as { toDate?: () => Date })?.toDate?.() ?? value;
        const date = raw instanceof Date ? raw : new Date(String(raw ?? ''));
        if (Number.isNaN(date.getTime())) return '-';
        return date.toLocaleString('es-CO', { hour12: false });
    }

    descargarTxt(): void {
        this.mensaje.set('');
        this.error.set('');

        const lineas = this.registros().validos;
        if (!lineas.length) {
            this.error.set('No hay registros MMV validos de Camara para descargar.');
            return;
        }

        const contenido = `${lineas.join('\r\n')}\r\n`;
        const blob = new Blob([contenido], { type: 'text/plain;charset=latin-1' });
        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.download = 'RESULTADOS_MMV.txt';
        anchor.click();
        URL.revokeObjectURL(url);

        this.mensaje.set(`TXT descargado con ${lineas.length} lineas MMV validas.`);
    }
}
