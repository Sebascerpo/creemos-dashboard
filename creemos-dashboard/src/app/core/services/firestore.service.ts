import { inject, Injectable, Injector, runInInjectionContext } from '@angular/core';
import {
    Firestore,
    collection,
    collectionData,
    doc,
    docData,
    getDocs,
    orderBy,
    query,
    QueryConstraint,
    setDoc,
    serverTimestamp,
    where
} from '@angular/fire/firestore';
import { catchError, map, Observable, of } from 'rxjs';
import { MesaReportada } from '../models/catalogo.model';

@Injectable({ providedIn: 'root' })
export class FirestoreService {
    private readonly db = inject(Firestore);
    private readonly injector = inject(Injector);

    private buildMesaDocId(mesaKey: string, corporacion: string): string {
        return `${mesaKey}_${corporacion}`;
    }

    private normalizeCorporacion(value: unknown): '001' | '002' | '' {
        const raw = String(value ?? '').trim().toLowerCase();
        if (raw === '001' || raw === '1' || raw === 'senado') return '001';
        if (raw === '002' || raw === '2' || raw === 'camara' || raw === 'cámara') return '002';
        return '';
    }

    col$<T>(path: string, constraints: QueryConstraint[] = []): Observable<T[]> {
        const ref = collection(this.db, path);
        const q = constraints.length ? query(ref, ...constraints) : ref;
        return collectionData(q, { idField: 'id' }).pipe(
            catchError((error) => {
                console.error(`Firestore col$ error (${path})`, error);
                return of([] as T[]);
            })
        ) as Observable<T[]>;
    }

    doc$<T>(path: string): Observable<T | null> {
        const ref = doc(this.db, path);
        return docData(ref, { idField: 'id' }).pipe(
            catchError((error) => {
                console.error(`Firestore doc$ error (${path})`, error);
                return of(null);
            })
        ) as Observable<T | null>;
    }

    async upsert(path: string, data: Record<string, unknown>): Promise<void> {
        const ref = doc(this.db, path);
        await runInInjectionContext(this.injector, () => setDoc(ref, { ...data, updated_at: serverTimestamp() }, { merge: true }));
    }

    async submitMesa(data: MesaReportada): Promise<void> {
        const targetCorp = this.normalizeCorporacion(data.corporacion);
        const [canonicalRef, sameMesaSnap] = await runInInjectionContext(this.injector, async () => {
            const canonical = doc(this.db, `mesas_reportadas/${this.buildMesaDocId(data.mesa_key, data.corporacion)}`);
            const snap = await getDocs(query(collection(this.db, 'mesas_reportadas'), where('mesa_key', '==', data.mesa_key)));
            return [canonical, snap] as const;
        });

        let targetRef = canonicalRef;
        let newestMs = -1;
        for (const item of sameMesaSnap.docs) {
            const payload = item.data() as Partial<MesaReportada>;
            const corp = this.normalizeCorporacion(payload.corporacion);
            if (corp !== targetCorp) continue;
            const ts = this.timestampMs(payload.timestamp);
            if (ts >= newestMs) {
                newestMs = ts;
                targetRef = runInInjectionContext(this.injector, () => doc(this.db, `mesas_reportadas/${item.id}`));
            }
        }

        await runInInjectionContext(this.injector, () =>
            setDoc(targetRef, {
                ...data,
                timestamp: serverTimestamp(),
                updated_at: serverTimestamp()
            })
        );
    }

    getMesasReportadas(): Observable<MesaReportada[]> {
        return this.col$<MesaReportada>('mesas_reportadas', [orderBy('timestamp', 'desc')]).pipe(map((rows) => this.deduplicarMesas(rows)));
    }

    getMesasByMunicipio(codMuni: string): Observable<MesaReportada[]> {
        return this.col$<MesaReportada>('mesas_reportadas', [where('cod_muni', '==', codMuni)]).pipe(map((rows) => this.deduplicarMesas(rows)));
    }

    async getMesaEstado(mesaKey: string): Promise<{ senado: boolean; camara: boolean }> {
        const sameMesaSnap = await runInInjectionContext(this.injector, async () => getDocs(query(collection(this.db, 'mesas_reportadas'), where('mesa_key', '==', mesaKey))));

        let senado = false;
        let camara = false;
        for (const item of sameMesaSnap.docs) {
            const payload = item.data() as Partial<MesaReportada>;
            const corp = this.normalizeCorporacion(payload.corporacion);
            if (corp === '001') senado = true;
            if (corp === '002') camara = true;
        }

        return { senado, camara };
    }

    private timestampMs(value: unknown): number {
        const raw = (value as { toDate?: () => Date })?.toDate?.() ?? value;
        const d = raw instanceof Date ? raw : new Date(String(raw ?? ''));
        const ms = d.getTime();
        return Number.isFinite(ms) ? ms : 0;
    }

    private deduplicarMesas(rows: MesaReportada[]): MesaReportada[] {
        const byKey = new Map<string, MesaReportada>();

        for (const row of rows) {
            const key = `${String(row.mesa_key ?? '')}|${this.normalizeCorporacion(row.corporacion)}`;
            if (!key) continue;

            const current = byKey.get(key);
            if (!current) {
                byKey.set(key, row);
                continue;
            }

            const currentTs = this.timestampMs(current.timestamp);
            const nextTs = this.timestampMs(row.timestamp);
            if (nextTs >= currentTs) {
                byKey.set(key, row);
            }
        }

        return [...byKey.values()].sort((a, b) => this.timestampMs(b.timestamp) - this.timestampMs(a.timestamp));
    }
}
