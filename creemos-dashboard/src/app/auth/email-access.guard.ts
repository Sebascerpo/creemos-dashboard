import { inject } from '@angular/core';
import { Auth, authState } from '@angular/fire/auth';
import { ActivatedRouteSnapshot, CanActivateFn, Router, UrlTree } from '@angular/router';
import { map, Observable, take } from 'rxjs';

export const emailAccessGuard: CanActivateFn = (route: ActivatedRouteSnapshot): Observable<boolean | UrlTree> => {
    const auth = inject(Auth);
    const router = inject(Router);
    const allowed = ((route.data['allowedEmails'] as string[] | undefined) ?? []).map((e) => e.trim().toLowerCase());

    return authState(auth).pipe(
        take(1),
        map((user) => {
            if (!user) return router.createUrlTree(['/auth/login']);
            const email = (user.email ?? '').trim().toLowerCase();
            if (!allowed.length || allowed.includes(email)) return true;
            return router.createUrlTree(['/e14']);
        })
    );
};
