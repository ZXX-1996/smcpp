'Fit SMC++ to data using the EM algorithm'
from __future__ import absolute_import, division, print_function
import numpy as np
import scipy.optimize
import pprint
import multiprocessing
import sys
import itertools
import sys
import time
from logging import getLogger
import os
import traceback

logger = getLogger(__name__)

# Package imports
from .. import _smcpp, util, estimation_tools
from ..model import SMCModel
from ..population import Population
from ..inference_service import DumbInferenceService as InferenceService
# from ..inference_service import InferenceService
from ..optimizer import PopulationOptimizer, TwoPopulationOptimizer
from ..logging import init_logging

np.set_printoptions(linewidth=120, suppress=True)

def init_parser(parser):
    '''Configure parser and parse args.'''
    # FIXME: argument groups not supported in subparsers
    pop_params = parser # parser.add_argument_group('population parameters')
    model = parser # parser.add_argument_group('model')
    hmm = parser # parser.add_argument_group('HMM and fitting parameters')
    model.add_argument('--pieces', type=str, help="span of model pieces", default="32*1")
    model.add_argument('--t1', type=float, nargs="+", help="span of first piece(s), in generations", default=[400.])
    model.add_argument('--tK', type=float, help="end-point of last piece, in generations", default=40000.)
    model.add_argument('--exponential-pieces', type=int, nargs="+", help="piece(s) which have exponential growth")
    hmm.add_argument('--thinning', help="emit full SFS every <k>th site", default=None, type=int, metavar="k")
    hmm.add_argument('--no-pretrain', help="do not pretrain model", action="store_true", default=False)
    hmm.add_argument('--M', type=int, help="number of hidden states", default=32)
    hmm.add_argument('--em-iterations', type=int, help="number of EM steps to perform", default=20)
    hmm.add_argument('--regularization-penalty', type=float, help="regularization penalty", default=None)
    hmm.add_argument('--regularizer', choices=["abs", "quadratic"], default="quadratic", help="type of regularization to apply")
    hmm.add_argument('--lbfgs-factor', type=float, help="stopping criterion for optimizer", default=1e9)
    hmm.add_argument('--Nmin', type=float, help="Lower bound on effective population size", default=1000)
    hmm.add_argument('--Nmax', type=float, help="Upper bound on effective population size", default=400000)
    hmm.add_argument('--span-cutoff', help="treat spans > as missing", default=100000, type=int)
    hmm.add_argument('--init-model', type=str, help="model to use as starting point in optimization")
    hmm.add_argument('--hidden-states', type=float, nargs="+")
    pop_params.add_argument('--N0', default=1e4, type=float, help="reference effective (diploid) population size to scale output.")
    pop_params.add_argument('--theta', type=float, 
            help="population-scaled mutation rate. default: watterson's estimator.")
    pop_params.add_argument('--rho', type=float, 
            help="population-scaled mutation rate. default: theta.")
    pop_params.add_argument("--fix-rho", default=False, action="store_true", 
            help="do not estimate recombination rate from data")
    pop_params.add_argument("--folded", action="store_true", default=False,
            help="use folded SFS for emission probabilites. useful if polarization is not known.")
    hmm.add_argument('--length-cutoff', help="omit sequences < cutoff", default=0, type=int)
    parser.add_argument("-p", "--second-population", nargs="+", widget="MultiFileChooser", 
            help="Estimate divergence time using data set(s) from a second subpopulation")
    parser.add_argument("-o", "--outdir", help="output directory", default=".", widget="DirChooser")
    parser.add_argument('-v', '--verbose', action='store_true', help="generate tremendous amounts of output")
    parser.add_argument('data', nargs="+", help="data file(s) in SMC++ format", widget="MultiFileChooser")

def validate_args(args):
    # perform some sanity checking on the args
    if args.theta is not None:
        pgm = args.theta / (2. * args.N0)
        if not (1e-12 <= pgm <= 1e-2):
            logger.warn("The per-generation mutation rate is calculated to be %g. Is this correct?" % pgm)

def main(args):
    'Main control loop for EM algorithm'
    ## Initialize the logger
    init_logging(args.outdir, args.verbose, os.path.join(args.outdir, ".debug.txt"))
    ## Save all the command line args and stuff
    logger.debug(sys.argv)
    logger.debug(args)
    
    ## Create output directory and dump all values for use later
    try:
        os.makedirs(args.outdir)
    except OSError:
        pass # directory exists

    ## Perform some validation on the arguments
    validate_args(args)

    ## Begin main script
    ## Step 1: load data and clean up a bit
    datasets_files = [args.data]
    if args.second_population:
        logger.info("Split estimation mode selected")
        datasets_files.append(args.second_population)
    
    ## Construct populations
    populations = [(dsf, args) for dsf in datasets_files]

    ## Initialize the "inference server"
    iserv = InferenceService(populations)

    npop = len(populations)
    if npop == 1:
        opt_klass = PopulationOptimizer
    elif npop == 2:
        opt_klass = TwoPopulationOptimizer
    else:
        raise RuntimeError("> 2 populations not currently supported")
    opt = opt_klass(iserv, args.outdir)

    # Run the optimizer
    opt.run(args.em_iterations, args.fix_rho)

    iserv.close()
