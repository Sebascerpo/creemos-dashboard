import { CommonModule } from '@angular/common';
import { Component, inject } from '@angular/core';
import { Router } from '@angular/router';
import { ButtonModule } from 'primeng/button';
import { AuthService } from './auth.service';

@Component({
    selector: 'app-profile',
    standalone: true,
    imports: [CommonModule, ButtonModule],
    template: `
        <section class="mx-auto max-w-xl space-y-4">
            <header>
                <h2 class="mb-1 text-2xl font-semibold">Perfil</h2>
                <p class="text-sm text-slate-500">Sesion activa en la plataforma electoral.</p>
            </header>

            <article class="rounded-xl border border-slate-200 p-4 dark:border-slate-700">
                <p class="text-sm"><strong>Email:</strong> {{ auth.currentUser()?.email || '-' }}</p>
                <p class="mt-1 text-sm"><strong>Rol:</strong> {{ auth.role() }}</p>
            </article>

            <button pButton type="button" label="Cerrar sesion" icon="pi pi-sign-out" severity="danger" (click)="cerrarSesion()"></button>
        </section>
    `
})
export class ProfilePage {
    readonly auth = inject(AuthService);
    private readonly router = inject(Router);

    async cerrarSesion(): Promise<void> {
        await this.auth.logout();
        await this.router.navigateByUrl('/auth/login');
    }
}
