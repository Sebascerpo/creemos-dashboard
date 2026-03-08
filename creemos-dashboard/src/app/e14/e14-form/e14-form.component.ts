import { CommonModule } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { CatalogoService } from '../../core/services/catalogo.service';
import { FirestoreService } from '../../core/services/firestore.service';
import { MmvBuilderService } from '../../core/services/mmv-builder.service';
import { E14FormData, Municipio, Puesto, CandidatoCatalogo, MesaReportada } from '../../core/models/catalogo.model';
import { AuthService } from '../../auth/auth.service';
import { ButtonModule } from 'primeng/button';
import { ConfirmDialogModule } from 'primeng/confirmdialog';
import { ConfirmationService } from 'primeng/api';
import { InputNumberModule } from 'primeng/inputnumber';
import { MessageModule } from 'primeng/message';
import { SelectModule } from 'primeng/select';
import { SelectButtonModule } from 'primeng/selectbutton';
import { TableModule } from 'primeng/table';

type CorpKey = 'senado' | 'camara';

@Component({
    selector: 'app-e14-form',
    standalone: true,
    imports: [CommonModule, FormsModule, SelectButtonModule, SelectModule, InputNumberModule, TableModule, ButtonModule, MessageModule, ConfirmDialogModule],
    providers: [ConfirmationService],
    templateUrl: './e14-form.component.html',
    styles: [
        `
            :host ::ng-deep .e14-select {
                width: 100%;
            }

            :host ::ng-deep .e14-select .p-select-label {
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }

            :host ::ng-deep .e14-select-panel .p-select-option {
                white-space: normal;
                line-height: 1.25rem;
                word-break: break-word;
            }
        `
    ]
})
export class E14FormComponent {
    private readonly catalogo = inject(CatalogoService);
    private readonly firestore = inject(FirestoreService);
    private readonly mmvBuilder = inject(MmvBuilderService);
    private readonly auth = inject(AuthService);
    private readonly confirmation = inject(ConfirmationService);

    corporacion = signal<CorpKey>('senado');
    corpOptions = [
        { label: 'SENADO', value: 'senado' as CorpKey },
        { label: 'CAMARA', value: 'camara' as CorpKey }
    ];
    municipios = computed(() => this.catalogo.getMunicipios());
    municipiosOptions = computed(() => this.municipios().map((m) => ({ label: m.nombre, value: m.cod })));
    municipio = signal<Municipio | null>(null);
    puestos = computed(() => {
        const m = this.municipio();
        return m ? this.catalogo.getPuestosByMunicipio(m.cod) : [];
    });
    puestosOptions = computed(() => this.puestos().map((p) => ({ label: p.nombre, value: `${p.zona}|${p.cod_puesto}` })));
    puesto = signal<Puesto | null>(null);
    mesas = computed(() => {
        const m = this.municipio();
        const p = this.puesto();
        if (!m || !p) return [];
        return this.catalogo.getMesasByPuesto(m.cod, p.zona, p.cod_puesto);
    });
    mesa = signal<number | null>(null);
    mesasOptions = computed(() => this.mesas().map((n) => ({ label: `Mesa ${n}`, value: n })));
    mesaEstado = signal<{ senado: boolean; camara: boolean }>({ senado: false, camara: false });
    enviando = signal(false);

    mensajeError = signal('');
    mensajeOk = signal('');
    ultimoPayload = signal<MesaReportada | null>(null);

    candidatos = computed<CandidatoCatalogo[]>(() => this.catalogo.getCandidatosByCorporacion(this.corporacion()));
    votos = signal<Record<string, number>>({});

    totalVotos = computed(() => Object.values(this.votos()).reduce((acc, n) => acc + (Number(n) || 0), 0));
    corporacionActualLabel = computed(() => (this.corporacion() === 'senado' ? 'Senado' : 'Camara'));
    corporacionAlternaLabel = computed(() => (this.corporacion() === 'senado' ? 'Camara' : 'Senado'));
    corporacionActualYaReportada = computed(() => (this.corporacion() === 'senado' ? this.mesaEstado().senado : this.mesaEstado().camara));
    corporacionAlternaYaReportada = computed(() => (this.corporacion() === 'senado' ? this.mesaEstado().camara : this.mesaEstado().senado));
    bloqueoCargaActual = computed(() => !!this.mesa() && this.corporacionActualYaReportada());
    estadoMesaTexto = computed(() => {
        const s = this.mesaEstado().senado ? 'SI' : 'NO';
        const c = this.mesaEstado().camara ? 'SI' : 'NO';
        if (this.corporacionActualYaReportada()) {
            return `Esta mesa ya tiene reporte previo. Senado: ${s} · Camara: ${c}. Para ${this.corporacionActualLabel()} no se permite un segundo envio en la misma mesa.`;
        }
        if (this.corporacionAlternaYaReportada()) {
            return `Esta mesa ya tiene reporte previo. Senado: ${s} · Camara: ${c}. Puedes cargar ${this.corporacionActualLabel()} sin afectar ${this.corporacionAlternaLabel()}.`;
        }
        return `Estado actual de la mesa. Senado: ${s} · Camara: ${c}.`;
    });
    alertaMesaBloqueadaTexto = computed(
        () =>
            `Ya existe votacion registrada para ${this.corporacionActualLabel()} en esta mesa. No puedes cargar candidatos para ${this.corporacionActualLabel()}.`
    );
    canSubmit = computed(() => {
        return !!(this.municipio() && this.puesto() && this.mesa() && this.totalVotos() > 0 && !this.enviando() && !this.bloqueoCargaActual());
    });

    constructor() {
        this.resetVotos();
    }

    onCorporacionChange(value: CorpKey): void {
        this.corporacion.set(value);
        this.municipio.set(null);
        this.puesto.set(null);
        this.mesa.set(null);
        this.mesaEstado.set({ senado: false, camara: false });
        this.mensajeError.set('');
        this.mensajeOk.set('');
        this.ultimoPayload.set(null);
        this.resetVotos();
    }

    onMunicipioChange(codMuni: string | null): void {
        if (!codMuni) {
            this.municipio.set(null);
            this.puesto.set(null);
            this.mesa.set(null);
            this.mesaEstado.set({ senado: false, camara: false });
            return;
        }
        const muni = this.municipios().find((m) => m.cod === codMuni) ?? null;
        this.municipio.set(muni);
        this.puesto.set(null);
        this.mesa.set(null);
        this.mesaEstado.set({ senado: false, camara: false });
    }

    onPuestoChange(value: string | null): void {
        if (!value) {
            this.puesto.set(null);
            this.mesa.set(null);
            this.mesaEstado.set({ senado: false, camara: false });
            return;
        }
        const [zona, codPuesto] = value.split('|');
        const p = this.puestos().find((row) => row.zona === zona && row.cod_puesto === codPuesto) ?? null;
        this.puesto.set(p);
        this.mesa.set(null);
        this.mesaEstado.set({ senado: false, camara: false });
    }

    async onMesaChange(numMesa: number | string | null): Promise<void> {
        const mesaNumerica = numMesa === null ? null : Number(numMesa);
        const mesaValida = mesaNumerica !== null && Number.isFinite(mesaNumerica) && mesaNumerica > 0 ? mesaNumerica : null;
        this.mesa.set(mesaValida);
        this.mesaEstado.set({ senado: false, camara: false });
        this.mensajeError.set('');
        if (!mesaValida) return;
        const m = this.municipio();
        const p = this.puesto();
        if (!m || !p) return;
        const key = this.mmvBuilder.buildMesaKey(m.cod, p.zona, p.cod_puesto, mesaValida);
        try {
            this.mesaEstado.set(await this.firestore.getMesaEstado(key));
        } catch (error) {
            this.mensajeError.set('No fue posible validar el estado previo de la mesa.');
        }
    }

    onVotoChange(codCandidato: string, raw: number | string | null): void {
        const parsed = Math.max(0, Math.floor(Number(raw) || 0));
        const next = { ...this.votos() };
        next[codCandidato] = parsed;
        this.votos.set(next);
    }

    getVoto(codCandidato: string): number {
        return this.votos()[codCandidato] ?? 0;
    }

    getNumeroCandidato(codCandidato: string, esLista: boolean): string {
        if (esLista) return '0';
        const n = Number(codCandidato);
        return Number.isFinite(n) ? String(n) : codCandidato;
    }

    private resetVotos(): void {
        const base: Record<string, number> = {};
        for (const c of this.candidatos()) {
            base[c.cod_candidato] = 0;
        }
        this.votos.set(base);
    }

    private buildFormData(): E14FormData {
        const municipio = this.municipio();
        const puesto = this.puesto();
        const mesa = this.mesa();
        if (!municipio || !puesto || !mesa) {
            throw new Error('Faltan selecciones obligatorias');
        }
        return {
            corporacion: this.corporacion(),
            municipio,
            puesto,
            num_mesa: mesa,
            votos: Object.entries(this.votos()).map(([cod_candidato, votos]) => ({
                cod_candidato,
                votos: Math.max(0, Number(votos) || 0)
            }))
        };
    }

    async enviarMesa(): Promise<void> {
        if (!this.canSubmit()) return;
        this.mensajeError.set('');
        this.mensajeOk.set('');
        this.enviando.set(true);

        try {
            if (this.bloqueoCargaActual()) {
                throw new Error(`La mesa ya tiene votacion registrada para ${this.corporacionActualLabel()}.`);
            }
            const data = this.buildFormData();
            const total = data.votos.reduce((acc, r) => acc + r.votos, 0);
            const ok = await this.confirmarEnvio(data, total);
            if (!ok) {
                this.enviando.set(false);
                return;
            }

            const circ = this.catalogo.getCircunscripcion(data.corporacion);
            const codPartido = this.catalogo.getPartidoCod(data.corporacion);
            const records = this.mmvBuilder.buildRecords(data, circ, codPartido);
            if (records.length === 0) {
                throw new Error('No hay votos mayores a cero para enviar');
            }

            const mesaKey = this.mmvBuilder.buildMesaKey(data.municipio.cod, data.puesto.zona, data.puesto.cod_puesto, data.num_mesa);
            const user = this.auth.currentUser();
            if (!user) {
                throw new Error('Sesion expirada. Inicia sesion nuevamente.');
            }
            const payload: MesaReportada = {
                mesa_key: mesaKey,
                cod_depto: '01',
                cod_muni: data.municipio.cod,
                nom_muni: data.municipio.nombre,
                zona: data.puesto.zona,
                cod_puesto: data.puesto.cod_puesto,
                nom_puesto: data.puesto.nombre,
                num_mesa: data.num_mesa,
                corporacion: data.corporacion === 'senado' ? '001' : '002',
                corporacion_nombre: data.corporacion === 'senado' ? 'SENADO' : 'CAMARA',
                circunscripcion: circ,
                cod_partido: codPartido,
                registros_mmv: records,
                total_votos: total,
                testigo_uid: user.uid,
                testigo_email: user.email ?? '',
                estado: 'enviado'
            };
            await this.firestore.submitMesa(payload);

            const keepCorp = this.corporacion();
            this.onCorporacionChange(keepCorp);
            this.ultimoPayload.set(payload);
            this.mensajeOk.set(`Mesa ${data.num_mesa} enviada correctamente (${records.length} registros MMV).`);
        } catch (error) {
            const message = this.humanizarErrorEnvio(error);
            this.mensajeError.set(message);
        } finally {
            this.enviando.set(false);
        }
    }

    private confirmarEnvio(data: E14FormData, total: number): Promise<boolean> {
        return new Promise((resolve) => {
            const mensajeBase = `Vas a enviar Mesa ${data.num_mesa} en ${data.puesto.nombre}, ${data.municipio.nombre}. Total votos: ${total}.`;
            this.confirmation.confirm({
                header: 'Confirmar envio E-14',
                icon: 'pi pi-exclamation-triangle',
                message: mensajeBase,
                acceptLabel: 'Enviar',
                rejectLabel: 'Cancelar',
                acceptButtonStyleClass: 'p-button-primary',
                rejectButtonStyleClass: 'p-button-text',
                accept: () => resolve(true),
                reject: () => resolve(false),
                closeOnEscape: true
            });
        });
    }

    private humanizarErrorEnvio(error: unknown): string {
        const code = String((error as { code?: string })?.code ?? '');
        const rawMessage = String((error as { message?: string })?.message ?? '');
        const msg = rawMessage.toLowerCase();

        if (code.includes('permission-denied')) {
            return 'No tienes permisos para guardar en Firestore. Verifica reglas y que el usuario logueado sea permitido.';
        }
        if (msg.includes('ya existe votacion registrada para')) {
            return rawMessage;
        }
        if (code.includes('unauthenticated')) {
            return 'Sesion no autenticada. Inicia sesion nuevamente.';
        }
        if (msg.includes('err_blocked_by_client') || msg.includes('blocked_by_client')) {
            return 'El navegador bloqueo la conexion a Firestore (ERR_BLOCKED_BY_CLIENT). Desactiva AdBlock/Brave Shields para este sitio.';
        }
        if (code.includes('unavailable') || code.includes('network-request-failed')) {
            return 'No fue posible conectar con Firestore. Revisa internet o bloqueadores del navegador.';
        }
        return error instanceof Error ? error.message : 'No fue posible enviar la mesa';
    }
}
