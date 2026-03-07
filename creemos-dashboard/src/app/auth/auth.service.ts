import { computed, inject, Injectable } from '@angular/core';
import { toSignal } from '@angular/core/rxjs-interop';
import { Auth, authState, signInWithEmailAndPassword, signOut, User } from '@angular/fire/auth';

export const ADMIN_EMAIL = 'admin@gmail.com';
export const TESTIGO_EMAIL = 'testigos@gmail.com';

export type UserRole = 'admin' | 'testigo' | 'none';

@Injectable({ providedIn: 'root' })
export class AuthService {
    private readonly auth = inject(Auth);

    readonly user = toSignal(authState(this.auth), { initialValue: null as User | null });
    readonly email = computed(() => (this.user()?.email ?? '').trim().toLowerCase());
    readonly role = computed<UserRole>(() => this.resolveRole(this.email()));
    readonly isAuthenticated = computed(() => !!this.user());
    readonly isAdmin = computed(() => this.role() === 'admin');
    readonly isTestigo = computed(() => this.role() === 'testigo');

    async login(email: string, password: string): Promise<void> {
        const cred = await signInWithEmailAndPassword(this.auth, email.trim(), password);
        const role = this.resolveRole(cred.user.email ?? '');
        if (role === 'none') {
            await signOut(this.auth);
            throw new Error('Este usuario no tiene permisos en la aplicacion.');
        }
    }

    async logout(): Promise<void> {
        await signOut(this.auth);
    }

    currentUser(): User | null {
        return this.user();
    }

    defaultRouteByRole(): string {
        const role = this.role();
        if (role === 'admin') return '/tracking';
        return '/e14';
    }

    resolveRole(email: string): UserRole {
        const normalized = (email ?? '').trim().toLowerCase();
        if (normalized === ADMIN_EMAIL) return 'admin';
        if (normalized === TESTIGO_EMAIL) return 'testigo';
        return 'none';
    }
}
