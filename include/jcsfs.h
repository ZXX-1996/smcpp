#ifndef JCSFS_H
#define JCSFS_H

#include <Eigen/Eigenvalues>

#include "common.h"
#include "conditioned_sfs.h"
#include "moran_eigensystem.h"
#include "mpq_support.h"

// This is a line-by line translation of the smcpp/jcsfs.py. See that
// file for motivating comments.
template <typename T>
class JointCSFS : public ConditionedSFS<T>
{
    public:
    JointCSFS(int n1, int n2, int a1, int a2, const std::vector<double> hidden_states) : 
        JointCSFS(n1, n2, a1, a2, hidden_states, 10) {}
    JointCSFS(int n1, int n2, int a1, int a2, const std::vector<double> hidden_states, int K) : 
        hidden_states(hidden_states),
        M(hidden_states.size() - 1),
        K(K), // number of random trials used to compute transition matrices.
        n1(n1), n2(n2), a1(a1), a2(a2), csfs(make_csfs()),
        togetherM(n1, n2),
        apartM(n1, n2),
        S2(arange(0, n1 + 2) / (n1 + 1)),
        S0(Vector<double>::Ones(n1 + 2) - S2),
        Sn1(arange(1, n1 + 2) / (n1 + 2)),
        J(M, Matrix<T>::Zero(a1 + 1, (n1 + 1) * (a2 + 1) * (n2 + 1))),
        hyp1(make_hyp1()), hyp2(make_hyp2())
        {}

    // This method exists for compatibility with the parent class interface. 
    std::vector<Matrix<T> > compute(const PiecewiseConstantRateFunction<T>&);
    // This method actually does the work and must be called before compute().
    void pre_compute(const ParameterVector&, const ParameterVector&, const double);
     
    private:
    struct jcsfs_eigensystem
    {
        jcsfs_eigensystem(const Matrix<mpq_class> &M) : 
            Md(M.template cast<double>()),
            es(Md, true), 
            U(es.eigenvectors().real()), Uinv(U.inverse()),
            D(es.eigenvalues().real()) {}
        const Matrix<double> Md;
        const Eigen::EigenSolver<Matrix<double> > es;
        const Matrix<double> U, Uinv;
        const Vector<double> D;

        const Matrix<T> expM(T t) const
        {
            Vector<T> eD = (t * D.template cast<T>()).array().exp().matrix();
            Matrix<T> ret = U.template cast<T>() * eD.asDiagonal() * Uinv.template cast<T>();
            return ret;
        }
    };
 
    struct togetherRateMatrices
    {
        togetherRateMatrices(const int n1, const int n2) :
            Mn1p1(moran_rate_matrix(n1 + 1)),
            Mn2(moran_rate_matrix(n2)),
            Mn10(modified_moran_rate_matrix(n1, 0, 2)),
            Mn11(modified_moran_rate_matrix(n1, 1, 2)),
            Mn12(modified_moran_rate_matrix(n1, 2, 2))
        {}
        jcsfs_eigensystem Mn1p1, Mn2, Mn10, Mn11, Mn12;
    };

    struct apartRateMatrices
    {
        apartRateMatrices(const int n1, const int n2) :
            Mn10(modified_moran_rate_matrix(n1, 0, 1)),
            Mn11(modified_moran_rate_matrix(n1, 1, 1)),
            Mn20(modified_moran_rate_matrix(n2, 0, 1)),
            Mn21(modified_moran_rate_matrix(n2, 1, 1))
        {}
        jcsfs_eigensystem Mn10, Mn11, Mn20, Mn21;
    };

    // Private functions
    inline T& tensorRef(const int m, const int i, const int j, const int k, const int l) 
    { 
        int ind = j * (n2 + 1) * (a2 + 1) + k * (n2 + 1) + l;
        return J[m].coeffRef(i, ind);
    }

    Vector<double> arange(int, int) const;

    void pre_compute_apart();
    void pre_compute_together();

    double scipy_stats_hypergeom_pmf(const int, const int, const int, const int);
    Matrix<double> make_hyp1();
    Matrix<double> make_hyp2();

    std::map<int, OnePopConditionedSFS<T> > make_csfs();
    Vector<double> make_S2();
    void jcsfs_helper_tau_above_split(const int, const double, const double, const T);
    void jcsfs_helper_tau_below_split(const int, const double, const double, const T);

    // Member variables
    const std::vector<double> hidden_states;
    const int M, K;
    const int n1, n2, a1, a2;
    std::map<int, OnePopConditionedSFS<T> > csfs;
    const togetherRateMatrices togetherM;
    const apartRateMatrices apartM;
    const Vector<double> S2, S0, Sn1;

    // These change at each call of compute
    std::vector<Matrix<T> > J;
    double split;
    T Rts1, Rts2;
    ParameterVector params1, params2;
    std::unique_ptr<PiecewiseConstantRateFunction<T> > eta1, eta2;
    std::array<Matrix<T>, 3> eMn1;
    Matrix<T> eMn2;
    const Matrix<double> hyp1, hyp2;
};

#endif
