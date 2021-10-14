from gym import Env
from gym.spaces import Box
from features import Feature
from stoppers import Stopper
from assessments import Assessment
from wtpy.WtBtEngine import WtBtEngine
from strategies import StateTransfer, EngineType

#一个进程只能有一个env
class EvaluatorWt(Env):
    _log_:str = './config/03research/log_evaluator.json'
    _dump_:bool = True

    def __init__(self, strategy:StateTransfer, feature:Feature, assessment:Assessment, stopper:Stopper, time_start:int, time_end:int, id:int=1):
        self._id_:int = id
        self._iter_:int = 0
        self._run_:bool = False 

        self.__strategy__ = strategy
        self._et_ = self.__strategy__.EngineType()

        self.__feature__:Feature = feature
        self.observation_space:Box = Box(**self.__feature__.observation)
        self.action_space:Box = Box(**self.__strategy__.Action(len(self.__feature__.securities)))
        
        self.__assessment__:Assessment = assessment
        self.__stopper__:Stopper = stopper


        # 创建一个运行环境
        self._engine_:WtBtEngine = WtBtEngine(
            eType=self._et_,
            logCfg=self._log_,
            )
        if self._et_ == EngineType.ET_CTA:
            self._engine_.init(
                './config/01commom/', 
                './config/03research/cta.json')
            self._cb_step_ = self._engine_.cta_step
        elif self._et_ == EngineType.ET_HFT:
            self._engine_.init(
                './config/01commom/', 
                './config/03research/hft.json')
            self._cb_step_ = self._engine_.hft_step
        else:
            raise AttributeError
        
        self._engine_.configBacktest(time_start, time_end)
        self._engine_.commitBTConfig()
        
    def reset(self):
        self.close()
        self._iter_ += 1

        # 重置奖励
        self.__assessment__.reset()

        # 创建一个策略并加入运行环境
        self._strategy_:StateTransfer = self.__strategy__(
            name=self._name_(),
            feature=self.__feature__,
            stopper=self.__stopper__,
            assessment=self.__assessment__,
            )

        # 设置策略的时候一定要安装钩子
        if self._et_ == EngineType.ET_CTA:
            self._engine_.set_cta_strategy(self._strategy_, slippage=1, hook=True, persistData=self._dump_)#
        elif self._et_ == EngineType.ET_HFT:
            self._engine_.set_hft_strategy(self._strategy_, hook=True)#
        else:
            raise AttributeError

        # 回测一定要异步运行
        self._engine_.run_backtest(bAsync=True, bNeedDump=self._dump_)
        self._run_ = True

        return self.step(None)[0]
    
    def step(self, action):
        assert self._iter_>0
        self._strategy_.setAction(action)
        finished = not self._cb_step_()
        if self.__assessment__.done or finished:
            self.__assessment__.finish()
            self.close()
        return self.__feature__.obs, self.__assessment__.reward, self.__assessment__.done, {}

    def close(self):
        if self._run_:
            self._engine_.stop_backtest()
            self._run_ = False

    def _name_(self):
        return '%s%s_%s%s'%(__class__.__name__, self._id_, self.__strategy__.Name(), self._iter_)

    def __del__(self):
        self._engine_.release_backtest()


class TrainWt(EvaluatorWt):
    _log_:str = './config/03research/log_train.json'
    _dump_:bool = False
    def _name_(self):
        return '%s%s_%s'%(__class__.__name__, self._id_, self.__strategy__.Name())