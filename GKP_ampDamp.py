# use S24 in stablization of Finite energy...
import warnings
warnings.filterwarnings("error")
import numpy as np
import math
import mpmath
from scipy.special import hermite,  eval_genlaguerre
from functools import lru_cache
from constants import *
import cvxpy as cp # https://www.cvxpy.org/examples/basic/sdp.html



# compute functions related to E_l \ket{\mu} basis
class GKP_ElmuBasis:
    def __init__(self,Delta,gamma,m_sum_cutoff,M_sum_cutoff,l_cut):
        self.gamma = gamma # damping rate gamma for amplitude damping channel
        self.Delta = Delta
        self.n_Delta = 1/(exp(2*Delta**2)-1) # approximate average phonon number
        self.m_sum_cutoff = m_sum_cutoff    # typically 20
        self.M_sum_cutoff = M_sum_cutoff    # typically 5
        self.l_cut = l_cut  # typically 20

    # metric of basis \ket{mu}, i.e. describe overlap and norm of GKP |0> |1>
    def m(self,keep_real = True):
        cutoff = self.m_sum_cutoff
        Delta = self.Delta
        cutoff = 20
        res = np.zeros((2,2),dtype=complex)
        for mu1 in [0,1]:
            for mu2 in [0,1]:
                for n1 in range(-cutoff,cutoff):
                    for n2 in range(-cutoff,cutoff):
                        Lambda = np.sqrt(np.pi/2)*(2*n1+mu1-mu2+1.j*n2)
                        res[mu1,mu2] += 1/(2*sqrt(np.pi)*(1-np.exp(-2*Delta**2)))* np.exp(1.j*np.pi*(n1+(mu1+mu2)/2)*n2)*np.exp(-1/(2*np.tanh(Delta**2))*abs(Lambda)**2) 
        # keep only real part
        if keep_real == True:
            res = res.real
        return np.matrix(res)

    def _lDl(self,l,lp,alpha):
        return lDl(l,lp,alpha)

    # metric of basis E_l \ket{mu}, i.e. describe overlap and norm of GKP E_l|0> E_l|1> , for l = 0,1,2,...
    # return a 2l_cutoff * 2l_cutoff dimentional matrix
    def _M(self,keep_real = True):
        sum_cutoff = self.M_sum_cutoff
        l_cutoff = self.l_cut
        Delta = self.Delta
        gamma = self.gamma
        res = np.zeros((2*l_cutoff,2*l_cutoff),dtype=complex)
        # element of M matrix
        def M_ele(cutoff,l,mu,lp,mup):
            n_D = 1/(exp(2*Delta**2)-1)
            factor = (gamma*n_D)**((l+lp)/2)/(gamma*n_D+1)**((l+lp)/2+1) / (2*sqrt(pi)*(1-exp(-2*Delta**2)))
            res = 0
            t = np.tanh(Delta**2/2)
            for n1 in range(-cutoff,cutoff):
                for n2 in range(-cutoff,cutoff):
                    Lambda = sqrt(pi/2)*(2*n1+mu-mup+n2*1.j)
                    alpha = exp(Delta**2)/sqrt(gamma+1/n_D)*conj(Lambda)
                    lDl = self._lDl(l,lp,alpha)
                    res += exp(-(1-gamma)/2/(gamma+1/n_D)*abs(Lambda)**2)*exp(1.j*pi*(n1+(mu+mup)/2)*n2)*lDl
            return (factor*res).real
        for i in range(2*l_cutoff):
            for j in range(2*l_cutoff):
                res[i,j] = M_ele(sum_cutoff, i//2, i%2, j//2, j%2)
        # keep only real part
        if keep_real == True:
            res = res.real
        return res

    # average photon number(rigorous result)
    def n_ave(self,sum_cutoff):
        Delta = self.Delta
        n_D = self.n_Delta
        factor = 0.5 / (2*sqrt(pi)*(1-exp(-2*Delta**2)))
        m0 = np.matrix([[m(Delta,mu,nu) for nu in [0,1]] for mu in [0,1]])
        cutoff = 20
        def K(Delta,mu,mup,cutoff):
            res = 0
            t2 = np.tanh(Delta**2)
            s2 = np.sinh(Delta**2)
            for n1 in range(-sum_cutoff,sum_cutoff):
                for n2 in range(-sum_cutoff,sum_cutoff):
                    Lambda = sqrt(pi/2)*(2*n1+mu-mup+n2*1.j)
                    alpha = exp(Delta**2)/sqrt(gamma+1/n_D)*conj(Lambda)
                    res += exp(-pi/(2*t2)*abs(Lambda)**2)*exp(1.j*pi*(n1+(mu+mup)/2)*n2)* abs(Lambda)**2 / 4 / s2**2
            return res
        K0 = np.matrix([[K(Delta,mu,nu,cutoff) for nu in [0,1]] for mu in [0,1]])
        return n_D - factor*np.trace(np.linalg.inv(m0)@K0)

    # transform into orthogonalized and normalized GKP basis
    def orth_M(self):
        Delta = self.Delta
        gamma = self.gamma
        Mmat = self._M()
        mmat = self.m()
        u, s, vh = np.linalg.svd(mmat, full_matrices=True)
        U = np.diag(np.array(s)**(-0.5))@vh
        U = np.kron(np.eye(self.l_cut), U)
        Mmat = U@Mmat@U.transpose()
        #print(U@Mmat@U.transpose())
        return Mmat

    # compute transpose fidelity with equation 
    def transpose_infid_M(self):
        Delta = self.Delta
        gamma = self.gamma
        dimL = self.l_cut
        #print('n_Delta',n_Delta(Delta))
        #print('n_ave',n_ave(Delta))
        #test_GKPstate_nBasis(Delta)
        #print('orth_M test',orth_M(Delta, 0, 3,5))
        Msqrt = scipy.linalg.sqrtm(self.orth_M())
        ptrMsqrt = Msqrt.reshape([dimL,2,dimL,2])
        ptrMsqrt = np.matrix([[ptrMsqrt[i,0,j,0]+ptrMsqrt[i,1,j,1] for j in range(dimL)] for i in range(dimL)])
        fid = 0.25*np.trace(ptrMsqrt@ptrMsqrt.transpose())
        #print(1-fid)
        return 1-fid

    def transpose_infid_approx(self,approxOrd):
        assert approxOrd in [0,1,2]
        Delta = self.Delta
        gamma = self.gamma
        t = tanh(Delta**2)
        n = self.n_Delta
        firstOrd = 2*exp(-pi/(4*t))*exp(-pi/4*(1-gamma)/(gamma+1/n)*(1+exp(2*Delta**2))) * exp(-gamma*n*exp(Delta**2)*sqrt(pi/2/(gamma+1/n)))
        A = gamma*n/(1+gamma*n)
        eps_gamma = 2*sqrt(2)*exp(-pi/4*(1-gamma)/(gamma+1/n))
        alpha1 = exp(Delta**2)*sqrt(pi/2/(gamma+1/n))
        secondOrd = 0
        k_cut = max(5,5*int(2*ln(2/((gamma+0.001)*n))/ln(A+0.0001)))
        for k in range(0,k_cut):
            for l in range(0,max(5,5*k)):
                if k - l != 0 and (k-l)%2 == 0 and A != 0.0:
                    secondOrd += A**(2*l+k)/(A**l-A**k)**2*abs(self._lDl(k,l, alpha1))**2
        secondOrd = eps_gamma**2/(1+gamma*n)*secondOrd
        result = [firstOrd,secondOrd]
        return sum(result[0:approxOrd])

    def eps_gamma(self):
        gamma = self.gamma
        n = self.n_Delta
        return 2*sqrt(2)*exp(-pi/4*(1-gamma)/(gamma+1/n))

    def eps_Delta(self):
        gamma = self.gamma
        n = self.n_Delta
        return sqrt(2)*exp(-pi/4/tanh(Delta**2))

# compute functions related to Fock state \ket{n} basis
class GKP_nBasis:
    def __init__(self,Delta,gamma,n_cutoff,sum_cutoff ):
        self.gamma = gamma # damping rate gamma for amplitude damping channel
        self.Delta = Delta
        self.n_Delta = 1/(exp(2*Delta**2)-1) # approximate average phonon number
        self.n_cutoff = n_cutoff
        self.sum_cutoff = sum_cutoff # typically 5

    # overlap between GKP state \ket{mu} and \ket{n}
    @lru_cache(1000)
    def _mu_n(self,mu,n):
        # result = exp(-Delta**2 * n) \sum_k \psi^*_n (2 pi**0.5 (k+mu/2)) where \psi_n is the n-th eigen state of harmonic ocillator
        Delta = self.Delta
        def psi(n,x): # normalization factor
            N = 1./np.sqrt(np.sqrt(np.pi))*1/np.sqrt(np.exp2(n))*1/np.sqrt(factorial(n))
            Hr=hermite(n)
            Psix = N*Hr(x)*np.exp(-0.5*x**2)
            return Psix
        cutoff = self.sum_cutoff
        return np.exp(-Delta**2*n)*sum([psi(n,2*np.sqrt(np.pi)*(i + mu/2)) for i in range(-cutoff,cutoff)])

    # GKP state \ket{mu} on n basis
    def _GKPstate(self,mu):
        assert mu in [0,1]
        return np.array([self._mu_n(mu,n) for n in range(self.n_cutoff)])

    # orthogonalize and normalize GKP states on n basis
    def get_othNor_basis(self):
        # generate GKP 0 and 1
        GKP0 = self._GKPstate(0)
        GKP1 = self._GKPstate(1)
        # obtain an normalized and orthogonal basis
        norm0 = np.linalg.norm(GKP0)**2
        norm1 = np.linalg.norm(GKP1)**2
        overlap = np.dot(GKP0,GKP1)
        basis0 = GKP0/np.sqrt(norm0)
        basis1 = GKP1 - overlap/norm0*GKP0
        basis1 = basis1/np.linalg.norm(basis1)
        return [basis0,basis1]

    # compute element \bra{n} E_l \ket{\mu} with finite energy(\Delta)
    @lru_cache(1000)
    def _Elmu_ele(self,n,l,mu):
        assert mu in [0,1]
        basis = self.get_othNor_basis()
        gamma = self.gamma
        Delta = self.Delta
        if n+l >= self.n_cutoff:
            return 0
        else:
            return gamma**(l/2) * (1-gamma)**(n/2) * np.sqrt(float(math.comb(n+l, n))) * basis[mu][n+l]

    # compute E_l \ket{mu}
    def Elmu(self,l,mu):
        return np.array([self._Elmu_ele(n,l,mu) for n in range(self.n_cutoff)])

    # compute N_\gamma(\ket{\mu}\ket{\nu}) , output a n_cut dimensional matrix
    # n_cut is a cut off for phonon number
    # with orthogonal and normalized basis
    def N_gamma_othNor(self,mu, nu, factor = 1):
        n_cut = self.n_cutoff
        result = np.zeros([n_cut,n_cut])
        for i in range(n_cut):
            for j in range(n_cut):
                l_range = n_cut - max(i,j)
                result[i,j] = sum([self._Elmu_ele(i,l,mu)*self._Elmu_ele(j,l,nu)*(factor **l) for l in range(l_range)])
        return result

    # use Pauli operator as input
    def N_gamma_othNor_pauli(self,pauli, factor = 1):
        N_gamma_othNor = self.N_gamma_othNor
        if pauli == 'I':
            return N_gamma_othNor(0,0, factor) + N_gamma_othNor(1,1, factor)
        elif pauli == 'X':
            return N_gamma_othNor(0,1, factor) + N_gamma_othNor(1,0, factor)
        elif pauli == 'Y':
            return -1.j*N_gamma_othNor(0,1, factor) + 1.j*N_gamma_othNor(1,0, factor)
        elif pauli == 'Z':
            return N_gamma_othNor(0,0, factor) - N_gamma_othNor(1,1, factor)
        else:
            raise TypeError('pauli operator type not found')

    # compute a parameter for SDP_optimization
    def _K_forSDP(self):
        #compute N_gamma_othNor_pauli(sigma_i)
        N_gamma_0 = self.N_gamma_othNor_pauli('I').transpose()
        N_gamma_1 = self.N_gamma_othNor_pauli('X').transpose()
        N_gamma_2 = self.N_gamma_othNor_pauli('Y').transpose()
        N_gamma_3 = self.N_gamma_othNor_pauli('Z').transpose()
        K = np.kron(N_gamma_0, sigma0) + np.kron(N_gamma_1, sigma1) + np.kron(N_gamma_2, sigma2) + np.kron(N_gamma_3, sigma3)
        K = 1/8*K.real# K should be real]
        return K


    # find an optimized recovery with SDP
    # use phonon number basis
    def SDP_optimize_Recovery_numberBasis(self,eps):
        n_cut = self.n_cutoff
        # the SDP problem is
        # max_R Tr 1/4 + 1/4 \sum_{i=x,y,z} A_i N_\gamma (\sigma_i)
        # R = 1/2 I_n \otimes I_code + \sum_{i=x,y,z} A_i \otimes \sigma_i >= 0
        #compute N_gamma_othNor_pauli(sigma_i)

        R = cp.Variable((n_cut*2,n_cut*2), symmetric=True)

        # compute partial trace of R
        constraints = [R >> 0]
        for i1 in range(n_cut):
            for j1 in range(n_cut):
                cons = np.zeros([n_cut*2,n_cut*2])
                for k in range(2):
                    cons[i1*2+k,j1*2+k] = 1
                constraints += [cp.trace(cons@R)==np.eye(n_cut)[i1,j1]]

        # solve SDP                
        prob = cp.Problem(
            cp.Maximize(cp.trace(self._K_forSDP()@R)),
            constraints
        )

        
        # optimization---')
        prob.solve(eps=eps)
        #print('---end optimization---')
        # result choi matrix 
        #choi = 1/2*cp.kron(A0,np.identity(2)) + cp.kron(A1, sigma1)+ cp.kron(A2, sigma2)+ cp.kron(A3, sigma3) 
        choi = None
        return prob.value, choi

# compare and check results between different basis
class check_basis:
    def __init__(self,ElmuBasis,nBasis):
        assert type(ElmuBasis) == GKP_ElmuBasis
        assert type(nBasis) == GKP_nBasis or nBasis == None
        self.Elmu = ElmuBasis
        self.n = nBasis
    def m(self):
        print('---','test m','---')
        Elmu_m = self.Elmu.m()
        print('Elmu Basis: m =',Elmu_m)
        nGKP0 = self.n._GKPstate(0)
        nGKP1 = self.n._GKPstate(1)
        nm00 = np.linalg.norm(nGKP0)**2
        nm11 = np.linalg.norm(nGKP1)**2
        nm01 = np.dot(nGKP0,nGKP1)
        n_m = np.matrix([[nm00,nm01],[nm01,nm11]])
        print('n Basis: m =',n_m)
        difference = np.linalg.norm(Elmu_m-n_m)
        print('---','difference',difference,'---')
    def M(self):
        print('---','test M','---')
        Elmu_M = self.Elmu.orth_M()
        print('Elmu Basis: M[0,0] =',Elmu_M[0,0])
        # inner product matrix element
        n_cut = self.n.n_cutoff
        n_M = np.zeros([n_cut*2,n_cut*2])
        for l1 in range(n_cut):
            for l2 in range(n_cut):
                for mu1 in range(2):
                    for mu2 in range(2):
                        n_M[l1*2+mu1,l2*2+mu2] = np.dot(self.n.Elmu(l1,mu1), self.n.Elmu(l2,mu2))
        print('n Basis: M[0,0] =',n_M[0,0])
        minD = min(len(Elmu_M),len(n_M))
        difference = np.linalg.norm(Elmu_M[:minD,:minD]-n_M[:minD,:minD])
        print('---','difference',difference,'---')

    # trace M = 2
    def trM(self):
        Elmu_M = self.Elmu.orth_M()
        print('tr(M)-2 =',Elmu_M.trace()[0,0]-2)

    # check m matrix using the theta function expression
    def _m_theta(self,Delta,mu,nu):
        #raise ValueError('not consistent in test2')
        if mu not in [0,1] or nu not in [0,1]:
            raise TypeError('mu ,nu must be 0 or 1')
        if mu ==nu:
            def theta(z,t):
                return mpmath.jtheta(3,pi*z,exp(1.j*pi*t))
            t = np.tanh(Delta**2)
            s = np.sinh(Delta**2)
            c = np.cosh(Delta**2)
            x1 = theta(0,4.j/t)
            x2 = theta(2.j*mu*t,4.j*t)
            x3 = theta(2.j/t,4.j/t)
            x4 = theta(2.j*(1-mu)*t,4.j*t)
            res = np.exp(-np.pi*t*mu)/np.sqrt(np.pi*(1-np.exp(-4*Delta**2)))*(x1*x2+np.exp(-np.pi/c/s)*x3*x4)
        else:
            t = np.tanh(Delta**2)
            s = np.sinh(Delta**2)
            c = np.cosh(Delta**2)
            x1 = mpmath.jtheta(3,t*np.pi*1.j,np.exp(-4*np.pi*t))
            x2 = mpmath.jtheta(3,-np.pi*1.j/t,np.exp(-4*np.pi/t))
            x3 = mpmath.jtheta(3,-t*np.pi*1.j,np.exp(-4*np.pi*t))
            x4 = mpmath.jtheta(3,np.pi*1.j/t,np.exp(-4*np.pi/t))
            res = np.exp(-np.pi/4*(t+1/t))/np.sqrt(np.pi*(1-np.exp(-4*Delta**2)))*(x1*x2+x3*x4)
        return float(res.real)

    def m_withTheta(self):
        print('---','test m','---')
        Delta = self.n.Delta
        thetam00 = self._m_theta(Delta,0,0)
        thetam11 = self._m_theta(Delta,1,1)
        thetam01 = self._m_theta(Delta,0,1)
        thetam10 = self._m_theta(Delta,1,0)
        theta_m = np.matrix([[thetam00,thetam01],[thetam10,thetam11]])
        print('theta method: m =',theta_m)
        nGKP0 = self.n._GKPstate(0)
        nGKP1 = self.n._GKPstate(1)
        nm00 = np.linalg.norm(nGKP0)**2
        nm11 = np.linalg.norm(nGKP1)**2
        nm01 = np.dot(nGKP0,nGKP1)
        n_m = np.matrix([[nm00,nm01],[nm01,nm11]])
        print('n Basis: m =',n_m)
        difference = np.linalg.norm(theta_m-n_m)
        print('---','difference',difference,'---')


    def test_completeness():
        raise TypeError('not complete yet')
        n_cut = 50
        Delta = 0.309
        gamma = 0.1
        M = np.zeros([n_cut*2,n_cut*2])
        for l1 in range(n_cut):
            for l2 in range(n_cut):
                for mu1 in range(2):
                    for mu2 in range(2):
                        M[l1*2+mu1,l2*2+mu2] = M_inner(l1,mu1,l2,mu2,Delta,n_cut,gamma)
        a,b = np.linalg.eig(M)
        print('M matrix:',a)
        # construct 'identity' matrix for the support of E_i \ket{mu} 
        v = np.zeros([n_cut,n_cut*2])
        for n in range(n_cut):
            for l in range(n_cut):
                for mu in range(2):
                    v[n,l*2+mu] = vec_l_mu(n,l,mu,Delta,gamma)
        I = v@np.linalg.inv(M)@v.transpose()
        a , b = np.linalg.eig(I)
        print('identity', a)






if __name__ == '__main__':
    
    dimL=20
    cutoff = 5
    infid_approx_Ord1_lst = []
    infid_approx_Ord2_lst = []
    for gamma in gamma_lst:
        ElmuBasis = GKP_ElmuBasis(Delta = Delta, gamma = gamma, m_sum_cutoff=20,M_sum_cutoff=5,l_cut=20)
        # check
        if 0:
            ck = check_basis(ElmuBasis = ElmuBasis,nBasis = None)
            ck.trM()
        infid_approx_Ord1 = ElmuBasis.transpose_infid_approx(approxOrd=1)
        infid_approx_Ord1_lst.append(infid_approx_Ord1)
        infid_approx_Ord2 = ElmuBasis.transpose_infid_approx(approxOrd=2)
        infid_approx_Ord2_lst.append(infid_approx_Ord2)
        print(infid_approx_Ord1,infid_approx_Ord2)
    print('infid_approx_Ord1_lst =',infid_approx_Ord1_lst)
    print('infid_approx_Ord2_lst =',infid_approx_Ord2_lst)


    '''
    for gamma in np.linspace(0,0.1,11):
        print('--- gamma =',gamma)
        Delta = 0.481
        dimL=20
        cutoff = 5
        ElmuBasis = GKP_ElmuBasis(Delta = Delta, gamma = gamma, m_sum_cutoff=20,M_sum_cutoff=5,l_cut=20)
        n_cut = 40
        i_cut = 10
        eps = 1e-6
        nBasis = GKP_nBasis(Delta, gamma, n_cut, sum_cutoff = 5)

        # check
        if 0:
            print('check:')
            ck = check_basis(ElmuBasis = ElmuBasis,nBasis = nBasis)
            ck.m()
            ck.m_withTheta()
            ck.M()

        # do optimization
        print('Elmu:',ElmuBasis.transpose_fid())
        res = 1-nBasis.SDP_optimize_Recovery_numberBasis(eps=eps)[0]
        print('SDP',res)
    '''

